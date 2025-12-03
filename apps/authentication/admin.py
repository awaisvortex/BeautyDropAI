"""
Authentication admin configuration
"""
from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
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
            'fields': ('first_name', 'last_name')
        }),
        ('Role & Status', {
            'fields': ('role', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    readonly_fields = ['clerk_user_id', 'email', 'created_at']
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('clerk_user_id', 'email', 'role', 'first_name', 'last_name'),
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
