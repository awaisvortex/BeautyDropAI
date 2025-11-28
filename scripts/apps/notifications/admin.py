"""
Notifications admin configuration
"""
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Notification
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
