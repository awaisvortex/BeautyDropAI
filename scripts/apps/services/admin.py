"""
Services admin configuration
"""
from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """
    Admin configuration for Service
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
