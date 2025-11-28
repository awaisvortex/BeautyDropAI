"""
Clients admin configuration
"""
from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin configuration for Client
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
