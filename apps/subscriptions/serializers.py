"""
Subscription and Payment serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Subscription, Payment
from datetime import datetime
from django.utils import timezone


class SubscriptionSerializer(serializers.ModelSerializer):
    """Output serializer for Subscription model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    @extend_schema_field(serializers.IntegerField)
    def get_days_remaining(self, obj):
        if obj.end_date:
            delta = obj.end_date - timezone.now()
            return max(0, delta.days)
        return None
    
    @extend_schema_field(serializers.BooleanField)
    def get_is_active(self, obj):
        return obj.status == 'active' and obj.end_date > timezone.now()
    
    days_remaining = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'user_email', 'user_name', 'user_type',
            'plan_type', 'amount', 'stripe_subscription_id',
            'stripe_customer_id', 'start_date', 'end_date',
            'trial_end_date', 'status', 'auto_renew', 'days_remaining',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'stripe_subscription_id', 'stripe_customer_id',
            'created_at', 'updated_at'
        ]
    
    def get_days_remaining(self, obj):
        if obj.end_date:
            delta = obj.end_date - timezone.now()
            return max(0, delta.days)
        return None
    
    def get_is_active(self, obj):
        return obj.status == 'active' and obj.end_date > timezone.now()


class SubscriptionCreateSerializer(serializers.Serializer):
    """Input serializer for creating subscriptions"""
    plan_type = serializers.ChoiceField(
        choices=['free', 'basic', 'premium', 'enterprise']
    )
    user_type = serializers.ChoiceField(choices=['client', 'customer'])


class PaymentSerializer(serializers.ModelSerializer):
    """Output serializer for Payment model"""
    subscription_plan = serializers.CharField(
        source='subscription.plan_type',
        read_only=True
    )
    user_email = serializers.EmailField(
        source='subscription.user.email',
        read_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'subscription', 'subscription_plan', 'user_email',
            'amount', 'payment_method', 'transaction_id',
            'stripe_payment_intent_id', 'status', 'payment_date',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'subscription', 'transaction_id',
            'stripe_payment_intent_id', 'created_at', 'updated_at'
        ]


class PaymentHistorySerializer(serializers.ModelSerializer):
    """Simplified payment serializer for history lists"""
    plan_type = serializers.CharField(source='subscription.plan_type', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'plan_type', 'amount', 'payment_method',
            'status', 'payment_date', 'created_at'
        ]


class CheckoutSessionCreateSerializer(serializers.Serializer):
    """Input serializer for creating Stripe checkout session"""
    plan_type = serializers.ChoiceField(
        choices=['basic', 'premium', 'enterprise'],
        help_text="Subscription plan type"
    )
    success_url = serializers.URLField(help_text="URL to redirect after successful payment")
    cancel_url = serializers.URLField(help_text="URL to redirect if payment is cancelled")


class CheckoutSessionResponseSerializer(serializers.Serializer):
    """Output serializer for checkout session response"""
    session_id = serializers.CharField()
    session_url = serializers.URLField()
    publishable_key = serializers.CharField()


class PaymentConfirmSerializer(serializers.Serializer):
    """Input serializer for confirming payment"""
    session_id = serializers.CharField()


class PaymentConfirmResponseSerializer(serializers.Serializer):
    """Output serializer for payment confirmation response"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    subscription = SubscriptionSerializer(required=False)
    payment = PaymentSerializer(required=False)


class StripeWebhookSerializer(serializers.Serializer):
    """Input serializer for Stripe webhook"""
    # Webhook payload is validated by Stripe signature
    pass


class InvoiceSerializer(serializers.Serializer):
    """Output serializer for invoice data"""
    invoice_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    invoice_pdf = serializers.URLField()
    created_date = serializers.DateTimeField()


class SubscriptionCancelSerializer(serializers.Serializer):
    """Input serializer for cancelling subscription"""
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    cancel_at_period_end = serializers.BooleanField(
        default=True,
        help_text="If true, subscription will be cancelled at the end of the billing period"
    )


class SubscriptionUpgradeSerializer(serializers.Serializer):
    """Input serializer for upgrading subscription"""
    new_plan_type = serializers.ChoiceField(
        choices=['basic', 'premium', 'enterprise']
    )
    prorate = serializers.BooleanField(
        default=True,
        help_text="If true, will prorate the charges"
    )
