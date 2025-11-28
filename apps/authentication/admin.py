"""
Authentication admin configuration
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for User model
    """
    list_display = ['email', 'full_name', 'role', 'is_active', 'email_verified', 'created_at']
    list_filter = ['role', 'is_active', 'email_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'clerk_user_id']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Clerk Integration', {
            'fields': ('clerk_user_id', 'email', 'email_verified')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone', 'avatar_url')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Important Dates', {
            'fields': ('last_login_at', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['clerk_user_id', 'created_at', 'updated_at', 'last_login_at']
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('clerk_user_id', 'email', 'role', 'first_name', 'last_name'),
        }),
    )
