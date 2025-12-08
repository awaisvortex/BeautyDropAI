"""
Subscription serializers for API endpoints.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import SubscriptionPlan, Subscription, SubscriptionHistory, Payment



class StripePriceImportSerializer(serializers.Serializer):
    """
    Serializer for importing subscription plans from Stripe.
    """
    stripe_price_id = serializers.CharField(
        max_length=255,
        help_text="Stripe Price ID (e.g. price_1234)"
    )
    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Optional: Custom name for the plan (overrides Stripe product name)"
    )


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for SubscriptionPlan model.
    Used for displaying available subscription tiers.
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'stripe_price_id', 'stripe_product_id',
            'amount', 'billing_period', 'description', 'features',
            'is_active', 'is_popular', 'display_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionPlanCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating subscription plans (admin only).
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'stripe_price_id', 'stripe_product_id',
            'amount', 'billing_period', 'description', 'features',
            'is_active', 'is_popular', 'display_order'
        ]
    
    def validate_stripe_price_id(self, value):
        """Ensure stripe_price_id is unique."""
        if self.instance:
            # Update - exclude current instance
            if SubscriptionPlan.objects.exclude(pk=self.instance.pk).filter(stripe_price_id=value).exists():
                raise serializers.ValidationError("A plan with this Stripe Price ID already exists.")
        else:
            # Create - check uniqueness
            if SubscriptionPlan.objects.filter(stripe_price_id=value).exists():
                raise serializers.ValidationError("A plan with this Stripe Price ID already exists.")
        return value


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Subscription model.
    Includes plan details and computed fields.
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'user_email', 'plan',
            'stripe_subscription_id', 'stripe_customer_id',
            'status', 'is_current',
            'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'cancelled_at',
            'days_remaining',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'stripe_subscription_id', 'stripe_customer_id',
            'created_at', 'updated_at'
        ]
    
    def get_days_remaining(self, obj):
        """Calculate days remaining in current period."""
        if obj.current_period_end:
            delta = obj.current_period_end - timezone.now()
            return max(0, delta.days)
        return None


class CurrentSubscriptionSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for current subscription with additional context.
    """
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_amount = serializers.DecimalField(
        source='plan.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    plan_features = serializers.JSONField(source='plan.features', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    shops_count = serializers.SerializerMethodField()
    can_create_shop = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan_name', 'plan_amount', 'plan_features',
            'status', 'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'days_remaining',
            'shops_count', 'can_create_shop'
        ]
    
    def get_days_remaining(self, obj):
        """Calculate days remaining."""
        if obj.current_period_end:
            delta = obj.current_period_end - timezone.now()
            return max(0, delta.days)
        return None
    
    def get_shops_count(self, obj):
        """Get number of shops owned by user."""
        try:
            return obj.user.client_profile.shops.count()
        except:
            return 0
    
    def get_can_create_shop(self, obj):
        """Check if user can create more shops."""
        return obj.status == 'active' and obj.is_current


class CheckoutSessionRequestSerializer(serializers.Serializer):
    """
    Serializer for checkout session creation request.
    """
    stripe_price_id = serializers.CharField(help_text="Stripe Price ID of the subscription plan")
    
    def validate_stripe_price_id(self, value):
        """Ensure plan exists and is active."""
        try:
            plan = SubscriptionPlan.objects.get(stripe_price_id=value)
            if not plan.is_active:
                raise serializers.ValidationError("This subscription plan is not available.")
            return value
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Subscription plan not found.")


class CheckoutSessionResponseSerializer(serializers.Serializer):
    """
    Serializer for checkout session response.
    """
    checkout_url = serializers.URLField(help_text="URL to redirect user to Stripe Checkout")
    session_id = serializers.CharField(help_text="Stripe Checkout Session ID")
    action = serializers.ChoiceField(
        choices=['new', 'upgrade'],
        help_text="Type of action (new subscription or upgrade)"
    )
    message = serializers.CharField(help_text="User-friendly message")


class CheckoutErrorSerializer(serializers.Serializer):
    """
    Serializer for checkout error responses (downgrade/same tier).
    """
    error = serializers.ChoiceField(
        choices=['downgrade_not_allowed', 'already_subscribed', 'validation_error']
    )
    message = serializers.CharField()
    current_plan = serializers.CharField(required=False)
    requested_plan = serializers.CharField(required=False)


class BillingPortalResponseSerializer(serializers.Serializer):
    """
    Serializer for billing portal session response.
    """
    portal_url = serializers.URLField(help_text="URL to Stripe billing portal")


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for subscription history records.
    """
    old_plan_name = serializers.CharField(source='old_plan.name', read_only=True, allow_null=True)
    new_plan_name = serializers.CharField(source='new_plan.name', read_only=True, allow_null=True)
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = SubscriptionHistory
        fields = [
            'id', 'action', 'old_plan_name', 'new_plan_name',
            'changed_by_email', 'reason', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SubscriptionCancelSerializer(serializers.Serializer):
    """
    Serializer for cancel subscription request.
    """
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for cancellation"
    )
    immediate = serializers.BooleanField(
        default=False,
        help_text="Cancel immediately (True) or at period end (False)"
    )


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment model.
    """
    subscription_plan = serializers.CharField(source='subscription.plan.name', read_only=True)
    user_email = serializers.EmailField(source='subscription.user.email', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'subscription', 'subscription_plan', 'user_email',
            'amount', 'payment_method', 'transaction_id',
            'stripe_payment_intent_id', 'stripe_invoice_id',
            'status', 'payment_date', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
