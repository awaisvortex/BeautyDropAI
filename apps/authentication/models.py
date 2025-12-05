"""
User model with Clerk integration
"""
from django.db import models
from apps.core.utils.constants import USER_ROLES, USER_ROLE_CUSTOMER
from .managers import UserManager


from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model integrated with Clerk authentication.
    Uses clerk_user_id as the primary key.
    """
    # Primary key - Clerk User ID
    clerk_user_id = models.CharField(max_length=255, primary_key=True)
    
    # Basic fields
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # User role
    role = models.CharField(
        max_length=20,
        choices=USER_ROLES,
        default=USER_ROLE_CUSTOMER
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    
    # Admin fields
    is_staff = models.BooleanField(default=False)
    # is_superuser provided by PermissionsMixin
    # last_login provided by AbstractBaseUser
    # password provided by AbstractBaseUser

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        """Return user's full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    # is_anonymous and is_authenticated provided by AbstractBaseUser
    
    def is_client(self):
        """Check if user is a client (salon owner)"""
        return self.role == 'client'
    
    def is_customer(self):
        """Check if user is a customer"""
        return self.role == 'customer'
