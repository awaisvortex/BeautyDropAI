"""
Redis cache client configuration
"""
from django.core.cache import cache
from typing import Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Wrapper for Redis cache operations
    """
    
    @staticmethod
    def get(key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        try:
            return cache.get(key)
        except Exception as e:
            logger.error(f"Error getting from cache: {str(e)}")
            return None
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Timeout in seconds (default 5 minutes)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return False
    
    @staticmethod
    def clear() -> bool:
        """
        Clear all cache
        
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    @staticmethod
    def get_or_set(key: str, default_func, timeout: int = 300) -> Any:
        """
        Get from cache or set if not exists
        
        Args:
            key: Cache key
            default_func: Function to call if key doesn't exist
            timeout: Timeout in seconds
            
        Returns:
            Cached or computed value
        """
        try:
            value = cache.get(key)
            if value is None:
                value = default_func()
                cache.set(key, value, timeout)
            return value
        except Exception as e:
            logger.error(f"Error in get_or_set: {str(e)}")
            return default_func()


# Singleton instance
redis_client = RedisClient()
