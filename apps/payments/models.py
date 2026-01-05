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


class ConnectedAccount(BaseModel):
    """
    Stripe Connect account for a client (salon owner).
    Enables direct payments to owners for advance booking deposits.
    
    One owner can have multiple shops, but one Connect account.
    """
    client = models.OneToOneField(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='connected_account',
        help_text="Client (salon owner) this Connect account belongs to"
    )
    
    # Stripe Connect account info
    stripe_account_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe Connect Account ID (acct_xxx)"
    )
    
    # Account status from Stripe
    charges_enabled = models.BooleanField(
        default=False,
        help_text="Whether the account can accept charges"
    )
    payouts_enabled = models.BooleanField(
        default=False,
        help_text="Whether the account can receive payouts"
    )
    details_submitted = models.BooleanField(
        default=False,
        help_text="Whether the owner has submitted all required details"
    )
    onboarding_complete = models.BooleanField(
        default=False,
        help_text="Whether onboarding is fully complete"
    )
    
    # Additional data
    business_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of business (individual, company)"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional data from Stripe account"
    )
    
    class Meta:
        db_table = 'connected_accounts'
        verbose_name = 'Connected Account'
        verbose_name_plural = 'Connected Accounts'
        indexes = [
            models.Index(fields=['stripe_account_id']),
            models.Index(fields=['charges_enabled']),
        ]
    
    def __str__(self):
        status = "✓" if self.charges_enabled else "✗"
        return f"{status} {self.client.business_name} - {self.stripe_account_id}"
    
    @property
    def is_ready_for_payments(self):
        """Check if account can receive payments."""
        return self.charges_enabled and self.details_submitted


class BookingPayment(BaseModel):
    """
    Advance payment record for booking deposits.
    
    Tracks the 10% (or configurable %) advance payment that customers
    pay to confirm their booking.
    """
    from apps.core.utils.constants import BOOKING_PAYMENT_STATUSES, BOOKING_PAYMENT_PENDING
    
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='advance_payment',
        help_text="Booking this payment is for"
    )
    
    # Stripe payment info
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe PaymentIntent ID (pi_xxx)"
    )
    
    # Payment amounts
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Advance payment amount"
    )
    currency = models.CharField(
        max_length=3,
        default='usd',
        help_text="Currency code (usd, gbp, etc.)"
    )
    
    # Where the payment goes
    destination_account = models.ForeignKey(
        ConnectedAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        help_text="Connected account receiving this payment"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=BOOKING_PAYMENT_STATUSES,
        default=BOOKING_PAYMENT_PENDING,
        db_index=True,
        help_text="Payment status"
    )
    
    # Timestamps
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was confirmed"
    )
    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was refunded"
    )
    
    # Refund info
    stripe_refund_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Refund ID if refunded (re_xxx)"
    )
    refund_reason = models.TextField(
        blank=True,
        help_text="Reason for refund"
    )
    
    # Additional data
    metadata = models.JSONField(
        default=dict,
        help_text="Additional payment data"
    )
    
    class Meta:
        db_table = 'booking_payments'
        verbose_name = 'Booking Payment'
        verbose_name_plural = 'Booking Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['status']),
            models.Index(fields=['destination_account', 'status']),
        ]
    
    def __str__(self):
        return f"{self.booking} - ${self.amount} ({self.status})"

