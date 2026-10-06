from typing import List, Optional

class EmbeddingsInterface:
    """
    Interface for generating embeddings from text using sentence-transformers.
    Loads the model lazily to save resources.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embeddings for a single string of text.
        
        Args:
            text (str): The input text.
            
        Returns:
            List[float]: The generated embedding vector (384 dimensions).
        """
        if not text:
            return [0.0] * 384
            
        model = self._get_model()
        vector = model.encode(text)
        return vector.tolist()
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of text strings.
        
        Args:
            texts (List[str]): The input texts.
            
        Returns:
            List[List[float]]: A list of embedding vectors.
        """
        if not texts:
            return []
            
        model = self._get_model()
        vectors = model.encode(texts)
        return vectors.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Alias for embed_documents."""
        return self.embed_documents(texts)

