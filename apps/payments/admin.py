"""
Payment app admin interface.
"""
from django.contrib import admin
from .models import StripeCustomer, WebhookLog


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    """Admin interface for Stripe customers."""
    list_display = ['user', 'stripe_customer_id', 'email', 'created_at']
    search_fields = ['user__email', 'stripe_customer_id', 'email']
    readonly_fields = ['user', 'stripe_customer_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User & Stripe', {
            'fields': ('user', 'stripe_customer_id', 'email')
        }),
        ('Payment Methods', {
            'fields': ('default_payment_method',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    """Admin interface for webhook logs (read-only)."""
    list_display = [
        'source', 'event_type', 'event_id', 'processed',
        'retry_count', 'created_at'
    ]
    list_filter = ['source', 'processed', 'event_type', 'created_at']
    search_fields = ['event_id', 'event_type', 'error_message']
    readonly_fields = [
        'source', 'event_type', 'event_id', 'payload',
        'processed', 'error_message', 'processing_time',
        'retry_count', 'last_retry_at', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        """Webhooks are created automatically."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deleting old logs for cleanup."""
        return request.user.is_superuser
    
    fieldsets = (
        ('Webhook Details', {
            'fields': ('source', 'event_type', 'event_id')
        }),
        ('Processing', {
            'fields': ('processed', 'error_message', 'processing_time', 'retry_count', 'last_retry_at')
        }),
        ('Payload', {
            'fields': ('payload',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
