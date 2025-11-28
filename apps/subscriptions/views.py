"""
Subscription and Payment views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings

from .models import Subscription, Payment
from .serializers import (
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
    PaymentSerializer,
    PaymentHistorySerializer,
    CheckoutSessionCreateSerializer,
    CheckoutSessionResponseSerializer,
    PaymentConfirmSerializer,
    PaymentConfirmResponseSerializer,
)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing subscriptions"""
    queryset = Subscription.objects.select_related('user')
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Users see only their own subscriptions
        return super().get_queryset().filter(user=self.request.user)
    
    @extend_schema(
        summary="List subscriptions",
        description="Get current user's subscriptions",
        responses={200: SubscriptionSerializer(many=True)},
        tags=['Payments - Customer']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get subscription details",
        description="Retrieve detailed information about a specific subscription",
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="Subscription not found")
        },
        tags=['Payments - Customer']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Cancel subscription",
        description="Cancel an active subscription",
        request=None,
        responses={
            200: SubscriptionSerializer,
            400: OpenApiResponse(description="Bad Request"),
            404: OpenApiResponse(description="Subscription not found")
        },
        tags=['Payments - Customer']
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a subscription"""
        subscription = self.get_object()
        
        if subscription.status == 'cancelled':
            return Response(
                {'error': 'Subscription is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Implement Stripe cancellation
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        subscription.save(update_fields=['status', 'auto_renew'])
        
        return Response(SubscriptionSerializer(subscription).data)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing payments"""
    queryset = Payment.objects.select_related('subscription__user')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Users see only their own payments
        return super().get_queryset().filter(subscription__user=self.request.user)
    
    @extend_schema(
        summary="List payments",
        description="Get current user's payment history",
        responses={200: PaymentSerializer(many=True)},
        tags=['Payments - Customer']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get payment details",
        description="Retrieve detailed information about a specific payment",
        responses={
            200: PaymentSerializer,
            404: OpenApiResponse(description="Payment not found")
        },
        tags=['Payments - Customer']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Payment history",
        description="Get simplified payment history for current user",
        responses={200: PaymentHistorySerializer(many=True)},
        tags=['Payments - Customer']
    )
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get payment history"""
        payments = self.get_queryset().order_by('-payment_date')
        serializer = PaymentHistorySerializer(payments, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create checkout session",
        description="Create a Stripe checkout session for subscription payment",
        request=CheckoutSessionCreateSerializer,
        responses={
            200: CheckoutSessionResponseSerializer,
            400: OpenApiResponse(description="Bad Request")
        },
        tags=['Payments - Customer']
    )
    @action(detail=False, methods=['post'])
    def create_checkout_session(self, request):
        """Create Stripe checkout session"""
        from infrastructure.integrations.stripe.client import stripe_client, STRIPE_PRICE_IDS
        
        serializer = CheckoutSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_type = serializer.validated_data['plan_type']
        success_url = serializer.validated_data['success_url']
        cancel_url = serializer.validated_data['cancel_url']
        
        # Get price ID for plan
        price_id = STRIPE_PRICE_IDS.get(plan_type)
        if not price_id:
            return Response(
                {'error': f'Invalid plan type: {plan_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create checkout session
        session = stripe_client.create_checkout_session(
            customer_email=request.user.email,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(request.user.id),
                'plan_type': plan_type,
            }
        )
        
        if not session:
            return Response(
                {'error': 'Failed to create checkout session'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'session_id': session.id,
            'session_url': session.url,
            'publishable_key': settings.STRIPE_PUBLISHABLE_KEY
        })
    
    @extend_schema(
        summary="Confirm payment",
        description="Confirm a payment after successful Stripe checkout",
        request=PaymentConfirmSerializer,
        responses={
            200: PaymentConfirmResponseSerializer,
            400: OpenApiResponse(description="Bad Request")
        },
        tags=['Payments - Customer']
    )
    @action(detail=False, methods=['post'])
    def confirm_payment(self, request):
        """Confirm payment"""
        serializer = PaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Implement actual payment confirmation with Stripe
        response_data = {
            'success': True,
            'message': 'Payment confirmed successfully'
        }
        
        return Response(response_data)
    
    @extend_schema(
        summary="Stripe webhook",
        description="Handle Stripe webhook events",
        request=None,
        responses={200: dict},
        tags=['Payments - Customer']
    )
    @action(detail=False, methods=['post'], permission_classes=[])
    def webhook(self, request):
        """Handle Stripe webhooks"""
        # TODO: Implement Stripe webhook handling
        return Response({'received': True})
