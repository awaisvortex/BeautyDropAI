"""
Custom authentication classes for Clerk
"""
from rest_framework import authentication
import jwt

from .models import User
from .services.clerk_service import clerk_service


class ClerkJWTAuthentication(authentication.BaseAuthentication):
    """
    Authentication class for Clerk JWT tokens (Bearer token)
    """
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Decode Clerk token
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}  # TODO: Implement proper JWKS verification
            )
            
            # Check if it's a Clerk token (has 'azp' claim)
            if 'azp' not in decoded:
                return None
            
            # Get or create user
            clerk_user_id = decoded.get('sub')
            if not clerk_user_id:
                return None
            
            try:
                user = User.objects.get(clerk_user_id=clerk_user_id)
            except User.DoesNotExist:
                # Fetch from Clerk API and create
                clerk_user_data = clerk_service.get_user(clerk_user_id)
                if clerk_user_data:
                    user_data = clerk_service.sync_user_data(clerk_user_data)
                    user = User.objects.create(**user_data)
                else:
                    # Fallback: create with minimal data from token
                    user = User.objects.create(
                        clerk_user_id=clerk_user_id,
                        email=decoded.get('email', f'{clerk_user_id}@clerk.temp'),
                        email_verified=decoded.get('email_verified', False)
                    )
            
            return (user, None)
            
        except jwt.DecodeError:
            return None
        except Exception:
            return None
    
    def authenticate_header(self, request):
        return 'Bearer realm="api"'


class ClerkUserIdAuthentication(authentication.BaseAuthentication):
    """
    Development-only authentication using X-Clerk-User-ID header.
    For Swagger testing convenience.
    """
    
    def authenticate(self, request):
        clerk_user_id = request.META.get('HTTP_X_CLERK_USER_ID')
        
        if not clerk_user_id:
            return None
        
        try:
            user = User.objects.get(clerk_user_id=clerk_user_id)
            return (user, None)
        except User.DoesNotExist:
            return None
    
    def authenticate_header(self, request):
        return 'X-Clerk-User-ID'
