from typing import List, Dict, Any

class TextChunker:
    """
    Service for splitting large documents into smaller text chunks for vectorization.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and < chunk_size")
            
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Split a list of documents into smaller chunks.
        
        Args:
            documents (List[Dict[str, Any]]): The documents to chunk.
            
        Returns:
            List[Dict[str, Any]]: A list of chunked documents.
        """
        chunked_documents = []
        
        for doc in documents:
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            
            if not text:
                continue
                
            start = 0
            text_length = len(text)
            
            while start < text_length:
                end = min(start + self.chunk_size, text_length)
                chunk_text = text[start:end]
                
                chunked_documents.append({
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_start": start,
                        "chunk_end": end
                    }
                })
                
                if end == text_length:
                    break
                    
                start += (self.chunk_size - self.chunk_overlap)
                
        return chunked_documents
