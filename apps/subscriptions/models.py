"""
Subscription models for managing subscription plans and user subscriptions.

This module contains:
- SubscriptionPlan: Defines subscription tiers (Starter, Professional, Enterprise)
- Subscription: User subscriptions with Stripe integration
- SubscriptionHistory: Tracks subscription changes over time
- Payment: Payment records for subscriptions
"""
from django.db import models
from apps.core.models import BaseModel


class SubscriptionPlan(BaseModel):
    """
    Subscription plan configuration (e.g., Starter, Professional, Enterprise).
    
    Plans are created by admins and linked to Stripe Price IDs.
    The amount field is used to determine upgrade/downgrade eligibility.
    """
    # Plan identification
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Plan name (e.g., 'Starter', 'Professional', 'Enterprise')"
    )
    
    # Stripe integration
    stripe_price_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe Price ID (price_xxx)"
    )
    stripe_product_id = models.CharField(
        max_length=255,
        help_text="Stripe Product ID (prod_xxx)"
    )
    
    # Pricing
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Monthly price in USD (used for tier comparison)"
    )
    billing_period = models.CharField(
        max_length=10,
        default='month',
        help_text="Billing frequency (month or year)"
    )
    
    # Plan details
    description = models.TextField(
        blank=True,
        help_text="Plan description for frontend display"
    )
    features = models.JSONField(
        default=list,
        help_text="List of features included in this plan"
    )
    
    # Display configuration
    is_active = models.BooleanField(
        default=True,
        help_text="Whether users can subscribe to this plan"
    )
    is_popular = models.BooleanField(
        default=False,
        help_text="Show 'Most Popular' badge"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for frontend display (lower = higher priority)"
    )
    
    class Meta:
        db_table = 'subscription_plans'
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['display_order', 'amount']
        indexes = [
            models.Index(fields=['stripe_price_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} (${self.amount}/month)"
    
    def can_upgrade_from(self, other_plan):
        """Check if this plan is an upgrade from another plan."""
        return self.amount > other_plan.amount if other_plan else True
    
    def can_downgrade_from(self, other_plan):
        """Check if this plan is a downgrade from another plan."""
        return self.amount < other_plan.amount if other_plan else False


class Subscription(BaseModel):
    """
    User subscription to a plan.
    
    Business Rules:
    - Only clients (salon owners) can have subscriptions
    - Only ONE subscription can have is_current=True per user
    - Multiple subscriptions can exist (previous ones ending at period end)
    - Upgrades: Create new subscription, mark old as non-current
    - Downgrades: Blocked - user must cancel first
    """
    # User relationship
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='subscriptions',
        to_field='clerk_user_id',
        help_text="User (client) who owns this subscription"
    )
    
    # Plan relationship
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        help_text="Subscription plan tier"
    )
    
    # Stripe integration
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe Subscription ID (sub_xxx)"
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        help_text="Stripe Customer ID (cus_xxx)"
    )
    stripe_latest_invoice = models.CharField(
        max_length=255,
        blank=True,
        help_text="Latest Stripe Invoice ID (in_xxx)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Subscription status: active, past_due, canceled, unpaid"
    )
    is_current = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is the user's current active subscription"
    )
    
    # Billing period
    current_period_start = models.DateTimeField(
        help_text="Current billing period start"
    )
    current_period_end = models.DateTimeField(
        help_text="Current billing period end"
    )
    
    # Cancellation
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether subscription will cancel at period end"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When subscription was cancelled"
    )
    
    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['is_current']),
        ]
    
    def __str__(self):
        current_marker = " (CURRENT)" if self.is_current else ""
        return f"{self.user.email} - {self.plan.name}{current_marker}"
    
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == 'active' and self.is_current
    
    def save(self, *args, **kwargs):
        """Override save to ensure only one current subscription per user."""
        if self.is_current:
            # Mark all other subscriptions for this user as not current
            Subscription.objects.filter(
                user=self.user,
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class SubscriptionHistory(BaseModel):
    """
    Tracks subscription changes for audit trail.
    
    Records when subscriptions are created, upgraded, downgraded,
    cancelled, or renewed.
    """
    # Subscription reference
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="The subscription that changed"
    )
    
    # Action details
    action = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Action: created, upgraded, downgraded, cancelled, renewed, expired"
    )
    
    # Plan changes
    old_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text="Previous plan (for upgrades/downgrades)"
    )
    new_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text="New plan (for upgrades/downgrades)"
    )
    
    # Who initiated the change
    changed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field='clerk_user_id',
        related_name='+',
        help_text="User who initiated the change (if manual)"
    )
    
    # Additional context
    reason = models.TextField(
        blank=True,
        help_text="Reason for the change"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional data (e.g., Stripe event data)"
    )
    
    class Meta:
        db_table = 'subscription_history'
        verbose_name = 'Subscription History'
        verbose_name_plural = 'Subscription Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'action']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.subscription.user.email} - {self.action} - {self.created_at}"


class Payment(BaseModel):
    """
    Payment record for subscription invoices.
    
    Tracks successful and failed payments from Stripe.
    """
    # Subscription relationship
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Subscription this payment is for"
    )
    
    # Payment amount
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Payment amount in USD"
    )
    
    # Payment details
    payment_method = models.CharField(
        max_length=50,
        help_text="Payment method type (e.g., 'card', 'bank_account')"
    )
    transaction_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique transaction identifier"
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Payment Intent ID (pi_xxx)"
    )
    stripe_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe Invoice ID (in_xxx)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Payment status: succeeded, failed, pending, refunded"
    )
    
    # Dates
    payment_date = models.DateTimeField(
        help_text="When payment was processed"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment data from Stripe"
    )
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['stripe_invoice_id']),
        ]
    
    def __str__(self):
        return f"{self.subscription.user.email} - ${self.amount} - {self.status}"
