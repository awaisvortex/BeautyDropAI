"""
Clerk API service for authentication
"""
import requests
import jwt
from django.conf import settings
from typing import Optional, Dict, Any
import logging
from apps.core.utils.constants import USER_ROLE_CLIENT, USER_ROLE_CUSTOMER

logger = logging.getLogger(__name__)


class ClerkService:
    """
    Service for interacting with Clerk API
    """
    
    def __init__(self):
        self.secret_key = settings.CLERK_SECRET_KEY
        self.api_url = settings.CLERK_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token from Clerk
        
        Args:
            token: JWT token from Authorization header
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            # Decode JWT without verification first to get the key ID
            unverified_header = jwt.get_unverified_header(token)
            
            # For development, we'll decode without verification
            # In production, you should fetch Clerk's public keys and verify
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}  # TODO: Implement proper verification
            )
            
            return decoded
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return None
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user details from Clerk
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            User data if found, None otherwise
        """
        try:
            url = f"{self.api_url}/users/{user_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get user from Clerk: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error fetching user from Clerk: {str(e)}")
            return None
    
    def sync_user_data(self, clerk_user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and format user data from Clerk response
        
        Args:
            clerk_user_data: User data from Clerk API
            
        Returns:
            Formatted user data for Django model
        """
        email_addresses = clerk_user_data.get('email_addresses', [])
        primary_email = next(
            (email['email_address'] for email in email_addresses if email.get('id') == clerk_user_data.get('primary_email_address_id')),
            email_addresses[0]['email_address'] if email_addresses else ''
        )
        
        # Extract role from public_metadata or unsafe_metadata
        # Default to customer if not specified or invalid
        public_metadata = clerk_user_data.get('public_metadata', {})
        unsafe_metadata = clerk_user_data.get('unsafe_metadata', {})
        
        clerk_role = public_metadata.get('role') or unsafe_metadata.get('role', '')
        
        role = USER_ROLE_CUSTOMER
        if clerk_role == 'client':
            role = USER_ROLE_CLIENT
        
        return {
            'clerk_user_id': clerk_user_data.get('id'),
            'email': primary_email,
            'first_name': clerk_user_data.get('first_name', ''),
            'last_name': clerk_user_data.get('last_name', ''),
            'avatar_url': clerk_user_data.get('image_url', ''),
            'email_verified': any(email.get('verification', {}).get('status') == 'verified' for email in email_addresses),
            'role': role,
        }


# Singleton instance
clerk_service = ClerkService()
