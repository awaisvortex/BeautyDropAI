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
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user from Clerk by email address
        
        Args:
            email: User's email address
            
        Returns:
            User data or None
        """
        try:
            url = f"{self.api_url}/users"
            params = {'email_address': [email]}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                users = response.json()
                if users and len(users) > 0:
                    return users[0]
                return None
            
            logger.warning(f"Failed to get user by email: {response.status_code}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error getting user by email from Clerk: {str(e)}")
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
    
    def create_invitation(
        self,
        email_address: str,
        redirect_url: str,
        public_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Clerk invitation (magic link email)
        
        Args:
            email_address: Staff member's email
            redirect_url: URL to redirect after signup (staff portal)
            public_metadata: {'role': 'staff', 'shop_id': '...', 'staff_member_id': '...'}
            
        Returns:
            Invitation data if successful, error dict with 'error' key otherwise
        """
        try:
            url = f"{self.api_url}/invitations"
            payload = {
                'email_address': email_address,
                'redirect_url': redirect_url,
                'public_metadata': public_metadata or {},
                'notify': True  # Send email via Clerk
            }
            logger.info(f"Creating invitation for {email_address} with redirect_url: {redirect_url}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info(f"Invitation created successfully for {email_address}")
                return response.json()
            
            error_detail = response.text
            try:
                error_json = response.json()
                if 'errors' in error_json and len(error_json['errors']) > 0:
                    error_detail = error_json['errors'][0].get('message', response.text)
            except Exception:
                pass
            
            logger.error(f"Failed to create invitation for {email_address}: {response.status_code} - {error_detail}")
            return {'error': error_detail, 'status_code': response.status_code}
            
        except requests.RequestException as e:
            logger.error(f"Error creating Clerk invitation: {str(e)}")
            return {'error': str(e), 'status_code': 500}
    
    def revoke_invitation(self, invitation_id: str) -> bool:
        """
        Revoke a pending invitation
        
        Args:
            invitation_id: Clerk invitation ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_url}/invitations/{invitation_id}/revoke"
            response = requests.post(url, headers=self.headers, timeout=10)
            
            return response.status_code == 200
            
        except requests.RequestException as e:
            logger.error(f"Error revoking invitation: {str(e)}")
            return False
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete user from Clerk
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_url}/users/{user_id}"
            response = requests.delete(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Deleted user {user_id} from Clerk")
                return True
            
            logger.warning(f"Failed to delete user {user_id}: {response.status_code}")
            return False
            
        except requests.RequestException as e:
            logger.error(f"Error deleting user from Clerk: {str(e)}")
            return False


# Singleton instance
clerk_client = ClerkClient()
