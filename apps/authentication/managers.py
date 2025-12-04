"""
Custom user manager for Clerk authentication
"""
from django.db import models


from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom user manager for Clerk-authenticated users.
    No password management needed.
    """
    
    def create_user(self, email, clerk_user_id=None, password=None, **extra_fields):
        """
        Create and save a user. 
        If clerk_user_id is not provided, generates a local one (for admins).
        """
        if not email:
            raise ValueError('The Email field must be set')
            
        # Generate local ID if not provided (for local admins)
        if not clerk_user_id:
            import uuid
            clerk_user_id = f"local_{uuid.uuid4()}"

        extra_fields.setdefault('is_active', True)
        
        user = self.model(
            clerk_user_id=clerk_user_id,
            email=self.normalize_email(email),
            **extra_fields
        )
        
        if password:
            user.set_password(password)
            
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with email and password.
        """
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password=password, **extra_fields)
    
    def normalize_email(self, email):
        """
        Normalize the email address by lowercasing the domain part.
        """
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            pass
        else:
            email = email_name.lower() + '@' + domain_part.lower()
        return email
