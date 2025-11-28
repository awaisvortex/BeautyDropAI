"""
Subscription and Payment models
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils.constants import (
    SUBSCRIPTION_STATUSES,
    SUBSCRIPTION_STATUS_TRIAL,
    SUBSCRIPTION_PLANS,
    PLAN_FREE,
    PAYMENT_STATUSES,
    PAYMENT_STATUS_PENDING
)


class Subscription(BaseModel):
    """
    Subscription model for both clients and customers
    """
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    
    user_type = models.CharField(max_length=20)  # 'client' or 'customer'
    
    plan_type = models.CharField(
        max_length=50,
        choices=SUBSCRIPTION_PLANS,
        default=PLAN_FREE
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    
    # Dates
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUSES,
        default=SUBSCRIPTION_STATUS_TRIAL,
        db_index=True
    )
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['stripe_subscription_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan_type}"


class Payment(BaseModel):
    """
    Payment model for subscription payments
    """
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment details
    payment_method = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=255, unique=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUSES,
        default=PAYMENT_STATUS_PENDING,
        db_index=True
    )
    
    # Dates
    payment_date = models.DateTimeField()
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.subscription.user.email} - {self.amount} - {self.status}"
