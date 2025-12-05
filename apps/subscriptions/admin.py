"""
Subscription admin interface.
"""
from django.contrib import admin
from .models import SubscriptionPlan, Subscription, SubscriptionHistory, Payment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for subscription plans."""
    list_display = [
        'name', 'amount', 'billing_period', 'is_active',
        'is_popular', 'display_order', 'created_at'
    ]
    list_filter = ['is_active', 'is_popular', 'billing_period']
    search_fields = ['name', 'stripe_price_id', 'stripe_product_id']
    ordering = ['display_order', 'amount']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'display_order')
        }),
        ('Pricing', {
            'fields': ('amount', 'billing_period')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_price_id', 'stripe_product_id')
        }),
        ('Features', {
            'fields': ('features', 'is_popular')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for subscriptions."""
    list_display = [
        'user', 'plan', 'status', 'is_current',
        'current_period_end', 'cancel_at_period_end', 'created_at'
    ]
    list_filter = ['status', 'is_current', 'cancel_at_period_end', 'created_at']
    search_fields = ['user__email', 'stripe_subscription_id', 'stripe_customer_id']
    readonly_fields = [
        'stripe_subscription_id', 'stripe_customer_id',
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('User & Plan', {
            'fields': ('user', 'plan')
        }),
        ('Stripe Details', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id', 'stripe_latest_invoice')
        }),
        ('Status', {
            'fields': ('status', 'is_current', 'cancel_at_period_end', 'cancelled_at')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    """Admin interface for subscription history."""
    list_display = ['subscription', 'action', 'old_plan', 'new_plan', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['subscription__user__email', 'reason']
    readonly_fields = ['subscription', 'action', 'old_plan', 'new_plan', 'changed_by', 'created_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        """History is created automatically, not manually."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deleting history."""
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for payments."""
    list_display = [
        'subscription', 'amount', 'status',
        'payment_method', 'payment_date', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'payment_date']
    search_fields = [
        'subscription__user__email', 'transaction_id',
        'stripe_payment_intent_id', 'stripe_invoice_id'
    ]
    readonly_fields = [
        'subscription', 'transaction_id', 'stripe_payment_intent_id',
        'stripe_invoice_id', 'created_at'
    ]
    ordering = ['-payment_date']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('subscription', 'amount', 'payment_method', 'status', 'payment_date')
        }),
        ('Transaction IDs', {
            'fields': ('transaction_id', 'stripe_payment_intent_id', 'stripe_invoice_id')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at'),
            'classes': ('collapse',)
        }),
    )
