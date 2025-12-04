"""
Subscription API views.

Provides endpoints for:
- Subscription plan management (admin)
- Checkout session creation
- Billing portal access
- Current subscription status
- Subscription history
- Subscription cancellation
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.shortcuts import get_object_or_404
from django.conf import settings

from apps.core.permissions import IsClient
from .models import SubscriptionPlan, Subscription, SubscriptionHistory, Payment
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionPlanCreateSerializer,
    SubscriptionSerializer,
    CurrentSubscriptionSerializer,
    CheckoutSessionRequestSerializer,
    CheckoutSessionResponseSerializer,
    CheckoutErrorSerializer,
    BillingPortalResponseSerializer,
    SubscriptionHistorySerializer,
    SubscriptionCancelSerializer,
    PaymentSerializer,
    StripePriceImportSerializer,
)
from .subscription_service import get_current_subscription, can_subscribe_to_plan
from apps.payments.stripe_service import StripeClient

logger = logging.getLogger(__name__)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing subscription plans.
    
    Admin endpoints for importing Plans from Stripe.
    Public endpoint for listing active plans.
    """
    queryset = SubscriptionPlan.objects.all().order_by('display_order', 'amount')
    
    def get_serializer_class(self):
        return SubscriptionPlanSerializer
    
    def get_permissions(self):
        """List is public, everything else requires admin."""
        if self.action == 'list':
            return [AllowAny()]
        return [IsAdminUser()]
    
    def get_queryset(self):
        """Show only active plans to non-admin users."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset
    
    @extend_schema(
        summary="List subscription plans",
        description="Get all available subscription plans (only active plans for non-admin)",
        responses={200: SubscriptionPlanSerializer(many=True)},
        tags=['Subscriptions - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get subscription plan details",
        description="Retrieve detailed information about a subscription plan",
        responses={
            200: SubscriptionPlanSerializer,
            404: OpenApiResponse(description="Plan not found")
        },
        tags=['Subscriptions - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Import plan from Stripe",
        description="Create or update a subscription plan by importing details from Stripe using Price ID (admin only)",
        request=StripePriceImportSerializer,
        responses={
            200: SubscriptionPlanSerializer,
            400: OpenApiResponse(description="Bad Request or Invalid Price ID"),
            403: OpenApiResponse(description="Forbidden - Admin only")
        },
        tags=['Subscriptions - Admin']
    )
    @action(detail=False, methods=['post'], url_path='import-from-stripe')
    def import_from_stripe(self, request):
        """Import subscription plan from Stripe."""
        serializer = StripePriceImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        price_id = serializer.validated_data['stripe_price_id']
        
        # Check if plan already exists
        if SubscriptionPlan.objects.filter(stripe_price_id=price_id).exists():
            return Response(
                {'error': 'A subscription plan with this Stripe Price ID already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch details from Stripe
        price_details = StripeClient.get_price_details(price_id)
        
        if not price_details:
            return Response(
                {'error': 'Invalid Stripe Price ID or unable to fetch details'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create SubscriptionPlan
        plan = SubscriptionPlan.objects.create(
            stripe_price_id=price_details['id'],
            name=price_details['product_name'],
            stripe_product_id=price_details['product_id'],
            amount=price_details['amount'],
            billing_period=price_details['interval'],
            description=price_details['product_description'] or '',
            is_active=price_details['active']
        )
        
        logger.info(f"Created subscription plan {plan.name} from Stripe Price {price_id}")
        
        return Response(SubscriptionPlanSerializer(plan).data)


class SubscriptionViewSet(viewsets.GenericViewSet):
    """
    ViewSet for subscription management.
    
    Provides endpoints for:
    - Creating checkout sessions
    - Accessing billing portal
    - Viewing current subscription
    - Viewing subscription history
    - Canceling subscriptions
    """
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = SubscriptionSerializer
    
    @extend_schema(
        summary="Create checkout session",
        description="Create Stripe checkout session for subscription purchase. Validates upgrade/downgrade rules.",
        request=CheckoutSessionRequestSerializer,
        responses={
            200: CheckoutSessionResponseSerializer,
            400: CheckoutErrorSerializer,
            403: OpenApiResponse(description="Forbidden - Clients only")
        },
        tags=['Subscriptions - Client']
    )
    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """
        Create Stripe checkout session.
        
        Validates:
        - Upgrades: Allowed
        - Downgrades: Blocked
        - Same tier: Blocked
        """
        serializer = CheckoutSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        logger.info(f"Validated data keys: {serializer.validated_data.keys()}")
        
        stripe_price_id = serializer.validated_data['stripe_price_id']
        plan = get_object_or_404(SubscriptionPlan, stripe_price_id=stripe_price_id, is_active=True)
        
        # Validate subscription eligibility
        can_subscribe, action, message = can_subscribe_to_plan(request.user, plan)
        
        if not can_subscribe:
            # Blocked - downgrade or same tier
            error_type = 'downgrade_not_allowed' if action == 'downgrade' else 'already_subscribed'
            current_sub = get_current_subscription(request.user)
            
            return Response(
                {
                    'error': error_type,
                    'message': message,
                    'current_plan': current_sub.plan.name if current_sub else None,
                    'requested_plan': plan.name
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create checkout session
        try:
            success_url = request.data.get('success_url', f"{settings.FRONTEND_URL}/subscription/success")
            cancel_url = request.data.get('cancel_url', f"{settings.FRONTEND_URL}/subscription/cancel")
            
            session = StripeClient.create_checkout_session(
                customer_email=request.user.email,
                price_id=plan.stripe_price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'plan_id': str(plan.id),
                    'clerk_user_id': request.user.clerk_user_id,
                }
            )
            
            if not session:
                return Response(
                    {'error': 'Failed to create checkout session'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Created checkout session {session.id} for {request.user.email} - {action} to {plan.name}")
            
            return Response({
                'checkout_url': session.url,
                'session_id': session.id,
                'action': action,
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}", exc_info=True)
            return Response(
                {'error': 'validation_error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Access billing portal",
        description="Create Stripe billing portal session for subscription management",
        responses={
            200: BillingPortalResponseSerializer,
            400: OpenApiResponse(description="No Stripe customer found"),
            403: OpenApiResponse(description="Forbidden - Clients only")
        },
        tags=['Subscriptions - Client']
    )
    @action(detail=False, methods=['post'])
    def portal(self, request):
        """
        Create Stripe billing portal session.
        
        Allows users to:
        - Update payment method
        - View invoices
        - Cancel subscription
        """
        try:
            # Get Stripe customer
            stripe_customer = request.user.stripe_customer
            
            return_url = request.data.get('return_url', f"{settings.FRONTEND_URL}/dashboard")
            
            portal_session = StripeClient.create_billing_portal_session(
                customer_id=stripe_customer.stripe_customer_id,
                return_url=return_url
            )
            
            if not portal_session:
                return Response(
                    {'error': 'Failed to create portal session'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Created billing portal session for {request.user.email}")
            
            return Response({
                'portal_url': portal_session.url
            })
            
        except Exception as e:
            logger.error(f"Error creating portal session: {str(e)}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="Get current subscription",
        description="Get details of user's current active subscription",
        responses={
            200: CurrentSubscriptionSerializer,
            404: OpenApiResponse(description="No active subscription")
        },
        tags=['Subscriptions - Client']
    )
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current active subscription."""
        subscription = get_current_subscription(request.user)
        
        if not subscription:
            return Response(
                {'message': 'No active subscription'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CurrentSubscriptionSerializer(subscription)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get subscription history",
        description="Get history of all subscription changes",
        responses={200: SubscriptionHistorySerializer(many=True)},
        tags=['Subscriptions - Client']
    )
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get subscription change history."""
        # Get all subscriptions for this user
        subscriptions = Subscription.objects.filter(user=request.user)
        
        # Get history for all subscriptions
        history = SubscriptionHistory.objects.filter(
            subscription__in=subscriptions
        ).select_related('old_plan', 'new_plan', 'changed_by').order_by('-created_at')
        
        serializer = SubscriptionHistorySerializer(history, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Cancel subscription",
        description="Cancel subscription (at period end or immediately)",
        request=SubscriptionCancelSerializer,
        responses={
            200: OpenApiResponse(description="Subscription cancelled"),
            400: OpenApiResponse(description="Bad Request"),
            404: OpenApiResponse(description="No active subscription")
        },
        tags=['Subscriptions - Client']
    )
    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel user's subscription."""
        subscription = get_current_subscription(request.user)
        
        if not subscription:
            return Response(
                {'error': 'No active subscription to cancel'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SubscriptionCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        immediate = serializer.validated_data.get('immediate', False)
        reason = serializer.validated_data.get('reason', '')
        
        try:
            # Cancel in Stripe
            if immediate:
                StripeClient.cancel_subscription(subscription.stripe_subscription_id)
                message = "Subscription cancelled immediately"
            else:
                StripeClient.cancel_at_period_end(subscription.stripe_subscription_id)
                message = "Subscription will cancel at period end"
            
            # Log cancellation reason
            if reason:
                SubscriptionHistory.objects.create(
                    subscription=subscription,
                    action='cancelled',
                    reason=reason,
                    changed_by=request.user
                )
            
            logger.info(f"Cancelled subscription {subscription.id} for {request.user.email} (immediate={immediate})")
            
            return Response({'message': message})
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing payment history.
    
    Read-only access to payment records.
    """
    permission_classes = [IsAuthenticated, IsClient]
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        """Filter payments for current user's subscriptions."""
        user_subscriptions = Subscription.objects.filter(user=self.request.user)
        return Payment.objects.filter(
            subscription__in=user_subscriptions
        ).select_related('subscription__plan').order_by('-payment_date')
    
    @extend_schema(
        summary="List payments",
        description="Get payment history for user's subscriptions",
        responses={200: PaymentSerializer(many=True)},
        tags=['Subscriptions - Client']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get payment details",
        description="Get details of a specific payment",
        responses={
            200: PaymentSerializer,
            404: OpenApiResponse(description="Payment not found")
        },
        tags=['Subscriptions - Client']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
