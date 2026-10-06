import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from fastapi.security import HTTPAuthorizationCredentials
from app.core.security import get_current_user, security_scheme
from app.schemas.rag import RAGSearchRequest, RAGSearchResponse, RAGHealthResponse, RAGSearchResultItem
from app.core.rag.embeddings import EmbeddingsInterface
from app.core.rag.vector_store import VectorStoreInterface
from app.core.rag.retrieval_service import RetrievalService

router = APIRouter()
logger = logging.getLogger(__name__)

# Singleton instances initialized on demand
_retrieval_service = None

def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        try:
            embeddings = EmbeddingsInterface()
            vector_store = VectorStoreInterface()
            _retrieval_service = RetrievalService(embeddings=embeddings, vector_store=vector_store)
        except Exception as e:
            logger.error(f"Failed to initialize RAG services: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="RAG services unavailable"
            )
    return _retrieval_service

@router.get("/health", response_model=RAGHealthResponse)
def get_rag_health(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> RAGHealthResponse:
    """
    Check the health and connection status of RAG dependencies (Embeddings and Vector DB).
    """
    try:
        service = get_retrieval_service()
        # Test vector store connection by checking if URL is present (or any minimal health check)
        vs_status = "connected" if service.vector_store.supabase_url else "disconnected"
        emb_status = "initialized" if service.embeddings else "uninitialized"
        
        return RAGHealthResponse(
            status="ok",
            vector_store=vs_status,
            embeddings=emb_status
        )
    except Exception as e:
        logger.error(f"RAG health check failed: {e}")
        return RAGHealthResponse(status="error", vector_store="error", embeddings="error")

@router.post("/search", response_model=RAGSearchResponse)
def search_rag(
    request: RAGSearchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    retrieval_service: RetrievalService = Depends(get_retrieval_service)
) -> RAGSearchResponse:
    """
    Retrieve relevant document chunks based on a semantic query.
    Requires an authenticated user token.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
        
    try:
        results = retrieval_service.retrieve_context(
            query=request.question,
            top_k=request.top_k,
            similarity_threshold=0.0,
            token=credentials.credentials
        )
        
        formatted_results = []
        for r in results:
            formatted_results.append(RAGSearchResultItem(
                content=r.get("content", ""),
                similarity=r.get("similarity", 0.0),
                metadata=r.get("metadata", {})
            ))
            
        return RAGSearchResponse(
            question=request.question,
            results=formatted_results
        )
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during retrieval."
        )
