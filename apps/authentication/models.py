"""
User model with Clerk integration
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import UUIDModel
from apps.core.utils.constants import USER_ROLES, USER_ROLE_CUSTOMER
from .managers import UserManager


class User(UUIDModel, AbstractUser):
    """
    Custom user model integrated with Clerk authentication
    """
    # Remove username field, use email instead
    username = None
    
    # Clerk integration
    clerk_user_id = models.CharField(max_length=255, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    
    # User role
    role = models.CharField(
        max_length=20,
        choices=USER_ROLES,
        default=USER_ROLE_CUSTOMER
    )
    
    # Profile fields
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar_url = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['clerk_user_id']
    
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
    
    def is_client(self):
        """Check if user is a client (salon owner)"""
        return self.role == 'client'
    
    def is_customer(self):
        """Check if user is a customer"""
        return self.role == 'customer'
