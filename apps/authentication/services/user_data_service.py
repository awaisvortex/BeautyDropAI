"""
Service for fetching real-time user data from Clerk API
"""
from typing import Optional
import logging
from .clerk_service import clerk_service

logger = logging.getLogger(__name__)


class UserDataService:
    """
    Service for fetching real-time user data from Clerk that we don't store in DB.
    """
    
    def get_user_avatar(self, clerk_user_id: str) -> str:
        """
        Fetch user avatar URL from Clerk API
        
        Args:
            clerk_user_id: Clerk user ID
            
        Returns:
            Avatar URL or empty string if not found
        """
        try:
            clerk_user_data = clerk_service.get_user(clerk_user_id)
            if clerk_user_data:
                return clerk_user_data.get('image_url', '')
            return ''
        except Exception as e:
            logger.error(f"Error fetching avatar for {clerk_user_id}: {str(e)}")
            return ''
    
    def get_user_phone(self, clerk_user_id: str) -> str:
        """
        Fetch user phone number from Clerk API
        
        Args:
            clerk_user_id: Clerk user ID
            
        Returns:
            Phone number or empty string if not found
        """
        try:
            clerk_user_data = clerk_service.get_user(clerk_user_id)
            if clerk_user_data:
                phone_numbers = clerk_user_data.get('phone_numbers', [])
                if phone_numbers:
                    # Get primary phone number
                    primary_phone_id = clerk_user_data.get('primary_phone_number_id')
                    for phone in phone_numbers:
                        if phone.get('id') == primary_phone_id:
                            return phone.get('phone_number', '')
                    # Fallback to first phone
                    return phone_numbers[0].get('phone_number', '')
            return ''
        except Exception as e:
            logger.error(f"Error fetching phone for {clerk_user_id}: {str(e)}")
            return ''
    
    def get_full_user_profile(self, clerk_user_id: str) -> dict:
        """
        Get complete user profile from Clerk
        
        Args:
            clerk_user_id: Clerk user ID
            
        Returns:
            Dictionary with avatar_url and phone
        """
        return {
            'avatar_url': self.get_user_avatar(clerk_user_id),
            'phone': self.get_user_phone(clerk_user_id),
        }


# Singleton instance
user_data_service = UserDataService()
