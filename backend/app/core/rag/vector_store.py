import logging
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreInterface:
    """
    Interface for interacting with the Supabase pgvector vector database.
    - Write/Ingestion/Cleanup operations use the trusted SUPABASE_SERVICE_ROLE_KEY.
    - Read/Search operations use the restricted SUPABASE_ANON_KEY (or client credentials).
    """
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        anon_key: Optional[str] = None,
        service_key: Optional[str] = None,
    ) -> None:
        self.supabase_url = (supabase_url or settings.SUPABASE_URL or "").rstrip('/')
        self.anon_key = anon_key or settings.SUPABASE_ANON_KEY or ""
        self.service_key = service_key or settings.SUPABASE_SERVICE_ROLE_KEY or self.anon_key

    @property
    def write_headers(self) -> Dict[str, str]:
        """Headers used for administrative write operations (INSERT, UPDATE, DELETE)."""
        key = self.service_key or self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @property
    def read_headers(self) -> Dict[str, str]:
        """Headers used for restricted read / search operations (SELECT, RPC)."""
        key = self.anon_key or self.service_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }



    @property
    def headers(self) -> Dict[str, str]:
        """Default headers for backwards compatibility."""
        return self.write_headers

    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Store documents and their corresponding vector embeddings in Supabase pgvector.
        Requires service-role privileges.
        """
        if not documents or not embeddings or len(documents) != len(embeddings):
            return

        if not self.supabase_url or not (self.service_key or self.anon_key):
            logger.warning("Supabase vector store configuration missing. Cannot add documents.")
            return

        with httpx.Client() as client:
            grouped = {}
            for doc, emb in zip(documents, embeddings):
                filename = doc.get("metadata", {}).get("filename", "Unknown Document")
                if filename not in grouped:
                    grouped[filename] = []
                grouped[filename].append((doc, emb))

            for filename, chunks in grouped.items():
                doc_payload = {
                    "title": filename,
                    "source": chunks[0][0].get("metadata", {}).get("source", ""),
                    "description": "Auto-imported clinical document",
                }

                doc_res = client.post(
                    f"{self.supabase_url}/rest/v1/clinical_documents",
                    headers=self.write_headers,
                    json=doc_payload,
                )

                if doc_res.status_code >= 400:
                    logger.error(
                        f"Failed to insert clinical document metadata for '{filename}' "
                        f"(HTTP {doc_res.status_code}): {doc_res.text}"
                    )
                    continue

                inserted_docs = doc_res.json()
                if not inserted_docs:
                    logger.error(f"No document record returned for '{filename}'")
                    continue
                doc_id = inserted_docs[0]["id"]

                chunks_payload = []
                for doc, emb in chunks:
                    chunks_payload.append({
                        "document_id": doc_id,
                        "content": doc.get("text", ""),
                        "metadata": doc.get("metadata", {}),
                        "embedding": emb,
                    })

                chunk_res = client.post(
                    f"{self.supabase_url}/rest/v1/document_chunks",
                    headers=self.write_headers,
                    json=chunks_payload,
                )

                if chunk_res.status_code >= 400:
                    logger.error(
                        f"Failed to insert vector chunks for '{filename}' "
                        f"(HTTP {chunk_res.status_code}): {chunk_res.text}"
                    )

    def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        match_threshold: float = 0.0,
        token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute similarity search against document_chunks via match_document_chunks RPC.
        Uses restricted read credentials or user token.
        """
        if not self.supabase_url or not (self.anon_key or self.service_key):
            logger.warning("Supabase vector store configuration missing. Cannot perform search.")
            return []

        payload = {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": limit,
        }
        
        headers = dict(self.read_headers)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            if token == self.service_key or token.startswith("sb_secret_"):
                headers["apikey"] = self.service_key



        with httpx.Client() as client:
            res = client.post(
                f"{self.supabase_url}/rest/v1/rpc/match_document_chunks",
                headers=headers,
                json=payload,
            )

            if res.status_code >= 400:
                logger.error(
                    f"Vector similarity search RPC error (HTTP {res.status_code}): {res.text}"
                )
                return []

            return res.json()

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a clinical document and cascade delete its chunks.
        Requires service-role privileges.
        """
        if not self.supabase_url or not (self.service_key or self.anon_key):
            return False

        with httpx.Client() as client:
            res = client.delete(
                f"{self.supabase_url}/rest/v1/clinical_documents?id=eq.{document_id}",
                headers=self.write_headers,
            )
            return res.status_code < 400

    def delete_document_by_title(self, title: str) -> bool:
        """
        Delete clinical documents matching a given title.
        Requires service-role privileges.
        """
        if not self.supabase_url or not (self.service_key or self.anon_key):
            return False

        with httpx.Client() as client:
            res = client.delete(
                f"{self.supabase_url}/rest/v1/clinical_documents?title=eq.{title}",
                headers=self.write_headers,
            )
            return res.status_code < 400
