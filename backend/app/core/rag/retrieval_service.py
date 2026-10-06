import logging
from typing import List, Dict, Any
from app.core.rag.embeddings import EmbeddingsInterface
from app.core.rag.vector_store import VectorStoreInterface

logger = logging.getLogger(__name__)

class RetrievalService:
    """
    Service for orchestrating the RAG retrieval pipeline.
    """
    def __init__(self, embeddings: EmbeddingsInterface = None, vector_store: VectorStoreInterface = None) -> None:
        self.embeddings = embeddings or EmbeddingsInterface()
        self.vector_store = vector_store or VectorStoreInterface()

    def retrieve_context(self, query: str, top_k: int = 5, similarity_threshold: float = 0.0, token: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a given user query.
        
        Args:
            query (str): The user's query.
            top_k (int): Number of top documents to retrieve.
            similarity_threshold (float): Minimum similarity score.
            
        Returns:
            List[Dict[str, Any]]: A list of relevant context documents.
        """
        if not query or not query.strip():
            return []
            
        try:
            query_embedding = self.embeddings.embed_text(query)
            
            results = self.vector_store.similarity_search(query_embedding, limit=top_k, match_threshold=similarity_threshold, token=token)
            
            if not results:
                return []
                
            filtered_results = []
            for res in results:
                score = res.get("similarity", 0.0)
                if score >= similarity_threshold:
                    filtered_results.append(res)
                    
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error in retrieval pipeline: {e}")
            return []
