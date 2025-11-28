"""
Clerk authentication middleware
"""
from django.utils.functional import SimpleLazyObject
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .services.token_service import token_service
from .services.clerk_service import clerk_service
from .models import User
import logging

logger = logging.getLogger(__name__)


def get_user_from_token(request):
    """
    Get or create user from Clerk token
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if not auth_header:
        return AnonymousUser()
    
    # Validate token
    token_payload = token_service.validate_bearer_token(auth_header)
    
    if not token_payload:
        return AnonymousUser()
    
    # Extract user ID
    clerk_user_id = token_service.extract_user_id(token_payload)
    
    if not clerk_user_id:
        return AnonymousUser()
    
    try:
        # Try to get existing user
        user = User.objects.get(clerk_user_id=clerk_user_id)
        
        # Update last login
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        return user
        
    except User.DoesNotExist:
        # Fetch user data from Clerk
        clerk_user_data = clerk_service.get_user(clerk_user_id)
        
        if not clerk_user_data:
            logger.warning(f"Could not fetch user data from Clerk for ID: {clerk_user_id}")
            return AnonymousUser()
        
        # Create new user
        user_data = clerk_service.sync_user_data(clerk_user_data)
        user = User.objects.create(**user_data)
        
        logger.info(f"Created new user from Clerk: {user.email}")
        return user
    
    except Exception as e:
        logger.error(f"Error in get_user_from_token: {str(e)}")
        return AnonymousUser()


class ClerkAuthenticationMiddleware:
    """
    Middleware to authenticate users via Clerk JWT tokens
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Attach user to request
        request.user = SimpleLazyObject(lambda: get_user_from_token(request))
        
        response = self.get_response(request)
        return response
