"""
Customers admin configuration
"""
from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Admin configuration for Customer
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
