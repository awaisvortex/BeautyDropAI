"""
Payment models for Stripe integration and webhook logging.

This module contains:
- StripeCustomer: Maps Clerk users to Stripe customers
- WebhookLog: Logs all webhook events for debugging and audit
"""
from django.db import models
from apps.core.models import BaseModel


class StripeCustomer(BaseModel):
    """
    Maps Clerk users to Stripe customers.
    
    When a user is created in Clerk, we automatically create a corresponding
    Stripe customer. This model maintains the mapping between the two systems.
    """
    # User relationship (one-to-one)
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='stripe_customer',
        to_field='clerk_user_id',
        help_text="User this Stripe customer belongs to"
    )
    
    # Stripe customer information
    stripe_customer_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe Customer ID (cus_xxx)"
    )
    email = models.EmailField(
        help_text="Email address registered with Stripe"
    )
    default_payment_method = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default payment method ID (pm_xxx)"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Additional data synced from Stripe"
    )
    
    class Meta:
        db_table = 'stripe_customers'
        verbose_name = 'Stripe Customer'
        verbose_name_plural = 'Stripe Customers'
        indexes = [
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.stripe_customer_id}"


class WebhookLog(BaseModel):
    """
    Logs all webhook events from Stripe and Clerk.
    
    Used for debugging, audit trail, and detecting processing failures.
    Each webhook event is logged with its full payload and processing status.
    """
    # Webhook source
    source = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Webhook source: 'stripe' or 'clerk'"
    )
    
    # Event details
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event type (e.g., 'customer.subscription.created')"
    )
    event_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique event ID from webhook provider"
    )
    
    # Event payload
    payload = models.JSONField(
        help_text="Full webhook payload (for debugging)"
    )
    
    # Processing status
    processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether webhook was successfully processed"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    processing_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Processing time in seconds"
    )
    
    # Retry tracking
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of times processing was retried"
    )
    last_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last retry attempt was made"
    )
    
    class Meta:
        db_table = 'webhook_logs'
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'event_type']),
            models.Index(fields=['processed']),
            models.Index(fields=['created_at']),
            models.Index(fields=['event_id']),
        ]
    
    def __str__(self):
        status = "✓" if self.processed else "✗"
        return f"{status} {self.source} - {self.event_type} - {self.created_at}"
    
    def mark_processed(self, processing_time=None):
        """Mark webhook as successfully processed."""
        self.processed = True
        self.processing_time = processing_time
        self.save(update_fields=['processed', 'processing_time'])
    
    def mark_failed(self, error_message):
        """Mark webhook processing as failed and increment retry count."""
        self.processed = False
        self.error_message = error_message
        self.retry_count += 1
        from django.utils import timezone
        self.last_retry_at = timezone.now()
        self.save(update_fields=['processed', 'error_message', 'retry_count', 'last_retry_at'])
