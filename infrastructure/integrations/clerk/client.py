"""
Clerk API client wrapper
"""
import requests
from django.conf import settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ClerkClient:
    """
    Wrapper for Clerk API client
    """
    
    def __init__(self):
        self.api_key = settings.CLERK_SECRET_KEY
        self.api_url = settings.CLERK_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user from Clerk
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            User data or None
        """
        try:
            url = f"{self.api_url}/users/{user_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
            logger.warning(f"Failed to get user: {response.status_code}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error getting user from Clerk: {str(e)}")
            return None
    
    def list_users(self, limit: int = 100, offset: int = 0) -> list:
        """
        List users from Clerk
        
        Args:
            limit: Number of users to return
            offset: Offset for pagination
            
        Returns:
            List of users
        """
        try:
            url = f"{self.api_url}/users"
            params = {'limit': limit, 'offset': offset}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
            logger.warning(f"Failed to list users: {response.status_code}")
            return []
            
        except requests.RequestException as e:
            logger.error(f"Error listing users from Clerk: {str(e)}")
            return []
    
    def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update user metadata in Clerk
        
        Args:
            user_id: Clerk user ID
            metadata: Metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_url}/users/{user_id}/metadata"
            response = requests.patch(
                url,
                headers=self.headers,
                json={'public_metadata': metadata},
                timeout=10
            )
            
            return response.status_code == 200
            
        except requests.RequestException as e:
            logger.error(f"Error updating user metadata: {str(e)}")
            return False


# Singleton instance
clerk_client = ClerkClient()
