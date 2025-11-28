"""
Subscriptions admin configuration
"""
from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Admin configuration for Subscription
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
