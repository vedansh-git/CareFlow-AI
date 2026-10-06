from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class RAGSearchRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The query string to search for.")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of results to return.")

class RAGSearchResultItem(BaseModel):
    content: str = Field(..., description="The chunk text.")
    similarity: float = Field(..., description="Cosine or Inner Product similarity score.")
    metadata: Dict[str, Any] = Field(..., description="Source document metadata (e.g., filename, chunk index).")

class RAGSearchResponse(BaseModel):
    question: str
    results: List[RAGSearchResultItem]

class RAGHealthResponse(BaseModel):
    status: str
    vector_store: str
    embeddings: str
