"""
Token validation service
"""
from typing import Optional
from .clerk_service import clerk_service
import logging

logger = logging.getLogger(__name__)


class TokenService:
    """
    Service for validating authentication tokens
    """
    
    @staticmethod
    def validate_bearer_token(auth_header: str) -> Optional[dict]:
        """
        Validate Bearer token from Authorization header
        
        Args:
            auth_header: Authorization header value
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        if not auth_header:
            return None
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            logger.warning("Invalid authorization header format")
            return None
        
        token = parts[1]
        return clerk_service.verify_token(token)
    
    @staticmethod
    def extract_user_id(token_payload: dict) -> Optional[str]:
        """
        Extract user ID from token payload
        
        Args:
            token_payload: Decoded JWT payload
            
        Returns:
            User ID if present, None otherwise
        """
        # Clerk uses 'sub' claim for user ID
        return token_payload.get('sub')


# Singleton instance
token_service = TokenService()
