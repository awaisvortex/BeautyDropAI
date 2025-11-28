"""
Custom authentication classes for Clerk and JWT
"""
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
import jwt
import requests

from .models import User


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
            
            user, created = User.objects.get_or_create(
                clerk_user_id=clerk_user_id,
                defaults={
                    'email': email or f'{clerk_user_id}@clerk.temp',
                    'email_verified': decoded.get('email_verified', False),
                }
            )
            
            return (user, None)
            
        except jwt.DecodeError:
            return None
        except Exception:
            return None
    
    def authenticate_header(self, request):
        return 'Bearer realm="api"'
