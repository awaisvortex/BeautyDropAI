"""
Embedding service for text vectorization using OpenAI.
"""
import logging
from typing import List
from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using OpenAI's embedding model."""
    
    def __init__(self):
        self._client = None
        self.model = "text-embedding-3-small"  # 1536 dimensions, cost-effective
    
    @property
    def client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector (1536 dimensions)
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embedding vectors for multiple texts (batch).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating embeddings batch: {e}")
            raise
