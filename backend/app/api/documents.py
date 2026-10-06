import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import get_current_user, security_scheme
from app.services.document_service import DocumentService
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Singleton
_document_service = None

def get_document_service() -> DocumentService:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service

class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str | None = None
    description: str | None = None
    created_at: str
    updated_at: str
    owner_id: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    is_private: bool = True
    rag_indexed: bool = False
    chunk_count: int = 0


class DownloadUrlResponse(BaseModel):
    url: str

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    doc_service: DocumentService = Depends(get_document_service)
):
    """List documents for the current user."""
    return await doc_service.list_documents(credentials.credentials, current_user.get("id"))

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    doc_service: DocumentService = Depends(get_document_service)
):
    """Upload a new document."""
    return await doc_service.upload_document(file, current_user["id"], credentials.credentials)

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    doc_service: DocumentService = Depends(get_document_service)
):
    """Delete a document by ID."""
    success = await doc_service.delete_document(credentials.credentials, document_id, current_user.get("id"))
    if success:
        return {"status": "success", "message": "Document deleted"}
    raise HTTPException(status_code=500, detail="Failed to delete document")

@router.get("/{document_id}/download", response_model=DownloadUrlResponse)
async def get_download_url(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    doc_service: DocumentService = Depends(get_document_service)
):
    """Get a short-lived download URL for a document."""
    # First get the document to find file_path
    docs = await doc_service.list_documents(credentials.credentials, current_user.get("id"))
    doc = next((d for d in docs if d["id"] == document_id), None)
    if not doc or not doc.get("file_path"):
        raise HTTPException(status_code=404, detail="Document not found or access denied")
        
    url = await doc_service.get_download_url(credentials.credentials, doc["file_path"])
    return DownloadUrlResponse(url=url)
