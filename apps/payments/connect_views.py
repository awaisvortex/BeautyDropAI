"""
Stripe Connect API views for shop owner onboarding.

Endpoints for:
- Creating Connect accounts
- Getting onboarding links
- Checking account status
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse

from django.conf import settings

from apps.core.permissions import IsClient
from apps.payments.models import ConnectedAccount
from apps.payments.stripe_connect import stripe_connect_client

import logging

logger = logging.getLogger(__name__)


@extend_schema(
    summary="Create Connect Account",
    description="""
    Create a Stripe Connect Express account for the shop owner.
    
    This is the first step in enabling the owner to receive advance payments.
    After creating the account, call the account-link endpoint to get the onboarding URL.
    """,
    responses={
        200: OpenApiResponse(description="Account created successfully"),
        400: OpenApiResponse(description="Account already exists or creation failed"),
    },
    tags=['Payments - Connect']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsClient])
def create_connect_account(request):
    """Create a Stripe Connect account for the authenticated shop owner."""
    user = request.user
    
    try:
        client = user.client_profile
    except Exception:
        return Response(
            {'error': 'User is not a client/shop owner'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if account already exists
    if hasattr(client, 'connected_account'):
        connected_account = client.connected_account
        return Response({
            'already_exists': True,
            'account_id': connected_account.stripe_account_id,
            'charges_enabled': connected_account.charges_enabled,
            'onboarding_complete': connected_account.onboarding_complete,
        })
    
    # Create Stripe Express account
    stripe_account = stripe_connect_client.create_express_account(
        email=user.email,
        business_name=client.business_name,
        metadata={
            'client_id': str(client.id),
            'user_id': user.clerk_user_id,
        }
    )
    
    if not stripe_account:
        return Response(
            {'error': 'Failed to create Stripe account'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Create local record
    connected_account = ConnectedAccount.objects.create(
        client=client,
        stripe_account_id=stripe_account.id,
        charges_enabled=stripe_account.charges_enabled,
        payouts_enabled=stripe_account.payouts_enabled,
        details_submitted=stripe_account.details_submitted,
    )
    
    logger.info(f"Created Connect account {stripe_account.id} for client {client.id}")
    
    return Response({
        'success': True,
        'account_id': connected_account.stripe_account_id,
        'charges_enabled': connected_account.charges_enabled,
    })


@extend_schema(
    summary="Get Onboarding Link",
    description="""
    Get a Stripe onboarding URL for the shop owner.
    
    Redirect the owner to this URL to complete identity verification
    and bank account setup. The URL expires after a short time.
    """,
    responses={
        200: OpenApiResponse(description="Onboarding URL returned"),
        400: OpenApiResponse(description="No Connect account found"),
    },
    tags=['Payments - Connect']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClient])
def get_account_link(request):
    """Get a Stripe onboarding link for the shop owner."""
    user = request.user
    
    try:
        client = user.client_profile
        connected_account = client.connected_account
    except Exception:
        return Response(
            {'error': 'No Connect account found. Create one first.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if already complete
    if connected_account.charges_enabled and connected_account.details_submitted:
        return Response({
            'already_complete': True,
            'message': 'Account setup is complete. You can now receive payments.',
            'charges_enabled': True,
        })
    
    # Generate return/refresh URLs
    frontend_url = settings.FRONTEND_URL
    return_url = f"{frontend_url}/dashboard/settings/payments?setup=complete"
    refresh_url = f"{frontend_url}/dashboard/settings/payments?setup=refresh"
    
    # Create onboarding link
    onboarding_url = stripe_connect_client.create_account_link(
        account_id=connected_account.stripe_account_id,
        return_url=return_url,
        refresh_url=refresh_url,
    )
    
    if not onboarding_url:
        return Response(
            {'error': 'Failed to create onboarding link'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return Response({
        'onboarding_url': onboarding_url,
        'message': 'Redirect user to this URL to complete setup'
    })


@extend_schema(
    summary="Get Connect Account Status",
    description="""
    Check the status of the shop owner's Connect account.
    
    Returns whether the account can receive payments and any
    pending requirements.
    """,
    responses={
        200: OpenApiResponse(description="Account status returned"),
        404: OpenApiResponse(description="No Connect account found"),
    },
    tags=['Payments - Connect']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClient])
def get_account_status(request):
    """Get the status of the shop owner's Connect account."""
    user = request.user
    
    try:
        client = user.client_profile
        connected_account = client.connected_account
    except Exception:
        return Response(
            {'has_account': False, 'message': 'No Connect account found'},
            status=status.HTTP_200_OK
        )
    
    # Get fresh status from Stripe
    stripe_status = stripe_connect_client.get_account_status(
        connected_account.stripe_account_id
    )
    
    # Update local record if status changed
    if 'error' not in stripe_status:
        changed = False
        if connected_account.charges_enabled != stripe_status['charges_enabled']:
            connected_account.charges_enabled = stripe_status['charges_enabled']
            changed = True
        if connected_account.payouts_enabled != stripe_status['payouts_enabled']:
            connected_account.payouts_enabled = stripe_status['payouts_enabled']
            changed = True
        if connected_account.details_submitted != stripe_status['details_submitted']:
            connected_account.details_submitted = stripe_status['details_submitted']
            changed = True
        
        if changed:
            connected_account.save()
    
    return Response({
        'has_account': True,
        'account_id': connected_account.stripe_account_id,
        'charges_enabled': connected_account.charges_enabled,
        'payouts_enabled': connected_account.payouts_enabled,
        'details_submitted': connected_account.details_submitted,
        'is_ready_for_payments': connected_account.is_ready_for_payments,
        'requirements': stripe_status.get('requirements', {}),
    })


@extend_schema(
    summary="Get Dashboard Link",
    description="""
    Get a link to the Stripe Express Dashboard for the shop owner.
    
    Allows owners to view their earnings, pending payouts, and settings.
    """,
    responses={
        200: OpenApiResponse(description="Dashboard URL returned"),
        400: OpenApiResponse(description="No Connect account found"),
    },
    tags=['Payments - Connect']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsClient])
def get_dashboard_link(request):
    """Get a link to the owner's Stripe Express Dashboard."""
    user = request.user
    
    try:
        client = user.client_profile
        connected_account = client.connected_account
    except Exception:
        return Response(
            {'error': 'No Connect account found'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    dashboard_url = stripe_connect_client.create_login_link(
        connected_account.stripe_account_id
    )
    
    if not dashboard_url:
        return Response(
            {'error': 'Failed to create dashboard link'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return Response({
        'dashboard_url': dashboard_url,
    })
