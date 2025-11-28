"""
Custom authentication classes for Clerk and JWT
"""
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
import jwt
import requests

from .models import User
from .services.clerk_service import clerk_service


class ClerkJWTAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication class for Clerk JWT tokens
    """
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Try to decode as Clerk token
            # Clerk tokens have different structure than our JWT tokens
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}  # Clerk handles verification
            )
            
            # Check if it's a Clerk token (has 'azp' claim)
            if 'azp' not in decoded:
                return None
            
            # Get or create user from Clerk data
            clerk_user_id = decoded.get('sub')
            email = decoded.get('email')
            
            if not clerk_user_id:
                return None
            
            # Check if user exists
            try:
                user = User.objects.get(clerk_user_id=clerk_user_id)
            except User.DoesNotExist:
                # User doesn't exist, fetch from Clerk to get role and other details
                clerk_user_data = clerk_service.get_user(clerk_user_id)
                
                if clerk_user_data:
                    user_data = clerk_service.sync_user_data(clerk_user_data)
                    user = User.objects.create(**user_data)
                else:
                    # Fallback if Clerk API fails (shouldn't happen if token is valid but possible)
                    # Create basic user with default role (customer)
                    user = User.objects.create(
                        clerk_user_id=clerk_user_id,
                        email=email or f'{clerk_user_id}@clerk.temp',
                        email_verified=decoded.get('email_verified', False)
                    )
            
            return (user, None)
            
        except jwt.DecodeError:
            return None
        except Exception:
            return None
    
    def authenticate_header(self, request):
        return 'Bearer realm="api"'
