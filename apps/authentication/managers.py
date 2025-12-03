"""
Custom user manager for Clerk authentication
"""
from django.db import models


class UserManager(models.Manager):
    """
    Custom user manager for Clerk-authenticated users.
    No password management needed.
    """
    
    def create_user(self, clerk_user_id, email, **extra_fields):
        """
        Create and save a user with Clerk ID and email.
        """
        if not clerk_user_id:
            raise ValueError('The Clerk User ID field must be set')
        if not email:
            raise ValueError('The Email field must be set')
        
        extra_fields.setdefault('is_active', True)
        
        user = self.model(
            clerk_user_id=clerk_user_id,
            email=self.normalize_email(email),
            **extra_fields
        )
        user.save(using=self._db)
        return user
    
    def create_superuser(self, clerk_user_id, email, **extra_fields):
        """
        Create and save a superuser with Clerk ID and email.
        """
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        
        return self.create_user(clerk_user_id, email, **extra_fields)
    
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
