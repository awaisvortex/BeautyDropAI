"""
Pinecone service for vector database operations.
"""
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class PineconeService:
    """
    Manages Pinecone vector database operations.
    Handles upserting, querying, and deleting vectors.
    """
    
    NAMESPACE_SHOPS = "shops"
    NAMESPACE_SERVICES = "services"
    
    def __init__(self):
        self._index = None
    
    @property
    def index(self):
        """Lazy load Pinecone index."""
        if self._index is None:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            self._index = pc.Index(settings.PINECONE_INDEX_NAME)
        return self._index
    
    def upsert_shop(self, shop, embedding: List[float]) -> bool:
        """
        Upsert a shop to Pinecone.
        
        Args:
            shop: Shop model instance
            embedding: Pre-computed embedding vector
            
        Returns:
            True if successful
        """
        try:
            # Build metadata
            services = shop.services.filter(is_active=True)
            service_names = ", ".join([s.name for s in services[:10]])
            categories = set(s.category for s in services if s.category)
            
            metadata = {
                "shop_id": str(shop.id),
                "shop_name": shop.name,
                "description": (shop.description or "")[:500],
                "city": shop.city,
                "state": shop.state or "",
                "country": shop.country,
                "is_verified": shop.is_verified,
                "rating": float(shop.average_rating),
                "total_reviews": shop.total_reviews,
                "services": service_names[:200],
                "categories": list(categories)[:5],
                "phone": shop.phone or "",
                "is_active": shop.is_active,
            }
            
            self.index.upsert(
                vectors=[{
                    "id": str(shop.id),
                    "values": embedding,
                    "metadata": metadata
                }],
                namespace=self.NAMESPACE_SHOPS
            )
            
            logger.info(f"Upserted shop {shop.name} to Pinecone")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting shop to Pinecone: {e}")
            return False
    
    def upsert_service(self, service, embedding: List[float]) -> bool:
        """
        Upsert a service to Pinecone.
        
        Args:
            service: Service model instance
            embedding: Pre-computed embedding vector
            
        Returns:
            True if successful
        """
        try:
            metadata = {
                "service_id": str(service.id),
                "shop_id": str(service.shop.id),
                "shop_name": service.shop.name,
                "service_name": service.name,
                "description": (service.description or "")[:500],
                "category": service.category or "",
                "price": float(service.price),
                "duration_minutes": service.duration_minutes,
                "is_active": service.is_active,
            }
            
            self.index.upsert(
                vectors=[{
                    "id": str(service.id),
                    "values": embedding,
                    "metadata": metadata
                }],
                namespace=self.NAMESPACE_SERVICES
            )
            
            logger.info(f"Upserted service {service.name} to Pinecone")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting service to Pinecone: {e}")
            return False
    
    def query(
        self,
        embedding: List[float],
        namespace: str = NAMESPACE_SHOPS,
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Query Pinecone for similar vectors.
        
        Args:
            embedding: Query embedding vector
            namespace: Namespace to query
            top_k: Number of results to return
            filter: Optional metadata filter
            min_score: Minimum similarity score
            
        Returns:
            List of matching results with metadata
        """
        try:
            query_params = {
                "vector": embedding,
                "top_k": top_k,
                "include_metadata": True,
                "namespace": namespace
            }
            
            if filter:
                query_params["filter"] = filter
            
            results = self.index.query(**query_params)
            
            # Filter by minimum score
            matches = [
                {
                    "id": m.id,
                    "score": m.score,
                    "metadata": m.metadata
                }
                for m in results.matches
                if m.score >= min_score
            ]
            
            return matches
            
        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            return []
    
    def delete(self, ids: List[str], namespace: str = NAMESPACE_SHOPS) -> bool:
        """
        Delete vectors from Pinecone.
        
        Args:
            ids: List of vector IDs to delete
            namespace: Namespace to delete from
            
        Returns:
            True if successful
        """
        try:
            self.index.delete(ids=ids, namespace=namespace)
            logger.info(f"Deleted {len(ids)} vectors from Pinecone")
            return True
        except Exception as e:
            logger.error(f"Error deleting from Pinecone: {e}")
            return False
