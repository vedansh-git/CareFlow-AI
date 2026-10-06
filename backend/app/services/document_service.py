import os
import uuid
import httpx
from typing import List, Dict, Any, Optional
from fastapi import UploadFile, HTTPException, status
import logging
from app.core.config import settings
from app.core.rag.document_loader import DocumentLoader
from app.core.rag.text_chunker import TextChunker
from app.core.rag.embeddings import EmbeddingsInterface
from app.core.rag.vector_store import VectorStoreInterface

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL.rstrip('/')
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY
        
        self.document_loader = DocumentLoader()
        self.text_chunker = TextChunker()
        self.embeddings = EmbeddingsInterface()
        self.vector_store = VectorStoreInterface()

    def get_user_headers(self, token: str) -> Dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def get_service_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def list_documents(self, token: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List documents for the user with verified ownership and RAG indexing count."""
        url = f"{self.supabase_url}/rest/v1/clinical_documents?select=*,document_chunks(count)&order=created_at.desc"
        if user_id:
            url += f"&owner_id=eq.{user_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                url,
                headers=self.get_service_headers()
            )
            if res.status_code >= 400:
                logger.error(f"Error listing documents: {res.text}")
                raise HTTPException(status_code=500, detail="Failed to list documents")
            
            raw_docs = res.json()
            formatted_docs = []
            for doc in raw_docs:
                chunks = doc.get("document_chunks") or []
                chunk_count = chunks[0].get("count", 0) if chunks and isinstance(chunks, list) and len(chunks) > 0 else 0
                doc_copy = dict(doc)
                doc_copy.pop("document_chunks", None)
                doc_copy["chunk_count"] = chunk_count
                doc_copy["rag_indexed"] = chunk_count > 0
                formatted_docs.append(doc_copy)
                
            return formatted_docs

    async def delete_document(self, token: str, document_id: str, user_id: Optional[str] = None) -> bool:
        """Delete document enforcing user ownership."""
        # 1. Fetch document to verify ownership and get file_path before deleting
        async with httpx.AsyncClient(timeout=15.0) as client:
            query = f"id=eq.{document_id}"
            if user_id:
                query += f"&owner_id=eq.{user_id}"
            res = await client.get(
                f"{self.supabase_url}/rest/v1/clinical_documents?{query}&select=file_path,owner_id",
                headers=self.get_service_headers()
            )
            docs = res.json()
            if not docs:
                raise HTTPException(status_code=404, detail="Document not found or access denied")
                
            file_path = docs[0].get("file_path")
            
            # 2. Delete from clinical_documents (chunks cascade in DB)
            del_res = await client.delete(
                f"{self.supabase_url}/rest/v1/clinical_documents?id=eq.{document_id}",
                headers=self.get_service_headers()
            )
            if del_res.status_code >= 400:
                logger.error(f"Error deleting DB record: {del_res.text}")
                raise HTTPException(status_code=500, detail="Failed to delete document metadata")
                
            # 3. Delete from storage if file_path exists
            if file_path:
                storage_del_res = await client.delete(
                    f"{self.supabase_url}/storage/v1/object/careflow_documents/{file_path}",
                    headers=self.get_service_headers()
                )
                if storage_del_res.status_code >= 400:
                    logger.warning(f"Failed to delete storage file {file_path}: {storage_del_res.text}")
                    
            return True

    async def upload_document(self, file: UploadFile, user_id: str, token: str) -> Dict[str, Any]:
        """Upload a file, index if text, and save metadata."""
        MAX_SIZE = 10 * 1024 * 1024 # 10MB
        ALLOWED_TYPES = ["application/pdf", "text/plain", "text/markdown", "image/jpeg", "image/png"]
        
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        if file_size > MAX_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
            
        content_type = file.content_type
        if content_type not in ALLOWED_TYPES and not file.filename.lower().endswith(('.md', '.txt', '.pdf', '.jpg', '.jpeg', '.png')):
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        is_text_doc = content_type in ["application/pdf", "text/plain", "text/markdown"] or file.filename.lower().endswith(('.md', '.txt', '.pdf'))
        
        # 1. Upload to Supabase Storage
        file_uuid = str(uuid.uuid4())
        ext = file.filename.split('.')[-1] if '.' in file.filename else ''
        file_path = f"{user_id}/{file_uuid}.{ext}" if ext else f"{user_id}/{file_uuid}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            storage_res = await client.post(
                f"{self.supabase_url}/storage/v1/object/careflow_documents/{file_path}",
                headers={
                    "apikey": self.service_key,
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": content_type or "application/octet-stream"
                },
                content=file_bytes
            )
            if storage_res.status_code >= 400:
                logger.error(f"Storage upload failed: {storage_res.text}")
                raise HTTPException(status_code=500, detail="Failed to upload file to storage")
        
        # 2. Insert into clinical_documents
        doc_payload = {
            "title": file.filename,
            "source": "Uploaded by user",
            "description": "User uploaded document",
            "owner_id": user_id,
            "file_path": file_path,
            "file_type": content_type,
            "file_size": file_size,
            "is_private": True
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            db_res = await client.post(
                f"{self.supabase_url}/rest/v1/clinical_documents",
                headers=self.get_service_headers(),
                json=doc_payload
            )
            if db_res.status_code >= 400:
                # Cleanup storage if db insert fails
                await client.delete(
                    f"{self.supabase_url}/storage/v1/object/careflow_documents/{file_path}",
                    headers=self.get_service_headers()
                )
                logger.error(f"DB insert failed: {db_res.text}")
                raise HTTPException(status_code=500, detail="Failed to save document metadata")
                
            inserted_docs = db_res.json()
            if not inserted_docs:
                raise HTTPException(status_code=500, detail="DB insert returned no data")
                
            inserted_doc = dict(inserted_docs[0])
            doc_id = inserted_doc["id"]
        
        inserted_doc["chunk_count"] = 0
        inserted_doc["rag_indexed"] = False

        # 3. Process and index chunks (if text) using service_role
        if is_text_doc:
            text_content = self.document_loader.extract_text_from_bytes(file_bytes, file.filename, content_type)
            if text_content and text_content.strip():
                try:
                    document_with_meta = {
                        "text": text_content,
                        "metadata": {
                            "filename": file.filename,
                            "source": "Uploaded by user",
                            "owner_id": user_id,
                            "document_id": doc_id
                        }
                    }
                    chunked_docs = self.text_chunker.chunk_documents([document_with_meta])
                    
                    if chunked_docs:
                        # Embed
                        texts = [chunk["text"] for chunk in chunked_docs]
                        embeddings = self.embeddings.embed_documents(texts)
                        
                        # Insert chunks using service_role
                        chunks_payload = []
                        for chunk, emb in zip(chunked_docs, embeddings):
                            chunks_payload.append({
                                "document_id": doc_id,
                                "content": chunk.get("text", ""),
                                "metadata": chunk.get("metadata", {}),
                                "embedding": emb,
                            })
                            
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            chunk_res = await client.post(
                                f"{self.supabase_url}/rest/v1/document_chunks",
                                headers=self.get_service_headers(),
                                json=chunks_payload
                            )
                            if chunk_res.status_code >= 400:
                                logger.error(f"Failed to insert chunks: {chunk_res.text}")
                            else:
                                inserted_doc["chunk_count"] = len(chunks_payload)
                                inserted_doc["rag_indexed"] = True
                except Exception as e:
                    logger.error(f"Error processing RAG for {file.filename}: {e}")
                    # We still return the document successfully uploaded, but with rag_indexed = False
        
        return inserted_doc

    async def get_download_url(self, token: str, file_path: str) -> str:
        """Get signed URL for downloading document."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                f"{self.supabase_url}/storage/v1/object/sign/careflow_documents/{file_path}",
                headers=self.get_service_headers(),
                json={"expiresIn": 3600}
            )
            if res.status_code >= 400:
                logger.error(f"Error generating download URL: {res.text}")
                raise HTTPException(status_code=500, detail="Failed to generate download link")
            
            signed_url = res.json().get("signedURL")
            if signed_url:
                return f"{self.supabase_url}/storage/v1{signed_url}"
            return ""

