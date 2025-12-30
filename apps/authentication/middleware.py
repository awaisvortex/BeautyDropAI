"""
Clerk authentication middleware
"""
from django.utils.functional import SimpleLazyObject
from django.contrib.auth.models import AnonymousUser
from .services.token_service import token_service
from .services.clerk_service import clerk_service
from .models import User
import logging

logger = logging.getLogger(__name__)


def sync_user_role_from_clerk(user, clerk_user_data):
    """
    Sync user role from Clerk metadata.
    Prevents role mismatches when user is deleted/recreated in Clerk.
    """
    if not clerk_user_data:
        return
    
    # Get role from Clerk metadata (unsafe_metadata takes priority)
    unsafe_metadata = clerk_user_data.get('unsafe_metadata', {})
    public_metadata = clerk_user_data.get('public_metadata', {})
    clerk_role = unsafe_metadata.get('role') or public_metadata.get('role')
    
    # Update role if different
    if clerk_role and clerk_role != user.role:
        old_role = user.role
        user.role = clerk_role
        user.save(update_fields=['role'])
        logger.info(f"Auto-synced role for {user.email}: {old_role} → {clerk_role}")


def get_user_from_auth_header(auth_header):
    """
    Get or create user from Authorization header.
    Auto-syncs role from Clerk on each authentication.
    """
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
        # Try to get existing user by clerk_user_id
        try:
            user = User.objects.get(clerk_user_id=clerk_user_id)
            
            # Fetch latest data from Clerk to sync role
            clerk_user_data = clerk_service.get_user(clerk_user_id)
            if clerk_user_data:
                sync_user_role_from_clerk(user, clerk_user_data)
            
            return user
            
        except User.DoesNotExist:
            pass
        
        # Fetch user data from Clerk
        clerk_user_data = clerk_service.get_user(clerk_user_id)
        
        if not clerk_user_data:
            logger.warning(f"Could not fetch user data from Clerk for ID: {clerk_user_id}")
            return AnonymousUser()
        
        # Extract email from Clerk data
        email_addresses = clerk_user_data.get('email_addresses', [])
        primary_email = next(
            (email['email_address'] for email in email_addresses 
             if email.get('id') == clerk_user_data.get('primary_email_address_id')),
            email_addresses[0]['email_address'] if email_addresses else ''
        )
        
        # Check if user exists with same email but different clerk_user_id
        # (user was deleted from Clerk and recreated)
        try:
            old_user = User.objects.get(email__iexact=primary_email)
            
            # clerk_user_id is the primary key, so we need to recreate the user
            old_clerk_id = old_user.clerk_user_id
            
            # Get role from Clerk metadata
            unsafe_metadata = clerk_user_data.get('unsafe_metadata', {})
            public_metadata = clerk_user_data.get('public_metadata', {})
            clerk_role = unsafe_metadata.get('role') or public_metadata.get('role')
            
            # Store old user data
            user_data = {
                'email': old_user.email,
                'first_name': clerk_user_data.get('first_name', old_user.first_name or ''),
                'last_name': clerk_user_data.get('last_name', old_user.last_name or ''),
                'role': clerk_role or old_user.role,  # Use Clerk role if available
                'is_active': old_user.is_active,
                'email_verified': True,
                'is_staff': old_user.is_staff,
                'is_superuser': old_user.is_superuser,
            }
            
            # Delete old user and create with new clerk_user_id
            old_user.delete()
            user = User.objects.create(
                clerk_user_id=clerk_user_id,
                **user_data
            )
            
            logger.info(f"Recreated user {user.email}: clerk_id {old_clerk_id} -> {clerk_user_id}, role: {user.role}")
            return user
            
        except User.DoesNotExist:
            pass
        
        # Create new user with synced data (including email_verified)
        user_data = clerk_service.sync_user_data(clerk_user_data)
        user = User.objects.create(**user_data)
        
        logger.info(f"Created new user from Clerk: {user.email}")
        return user
    
    except Exception as e:
        logger.error(f"Error in get_user_from_auth_header: {str(e)}")
        return AnonymousUser()


def get_user_from_token(request):
    """
    Get or create user from Clerk token.
    Wraps get_user_from_auth_header using request headers.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    return get_user_from_auth_header(auth_header)


class ClerkAuthenticationMiddleware:
    """
    Middleware to authenticate users via Clerk JWT tokens.
    Auto-syncs user role with Clerk on each authentication.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Attach user to request only if Authorization header is present
        if request.META.get('HTTP_AUTHORIZATION'):
            request.user = SimpleLazyObject(lambda: get_user_from_token(request))
        
        response = self.get_response(request)
        return response
