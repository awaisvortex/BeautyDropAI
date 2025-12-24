"""
Webhook views for Stripe and Clerk events.
"""
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .stripe_webhooks import process_stripe_webhook
from .clerk_webhooks import process_clerk_webhook
from .stripe_service import StripeClient

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Handle incoming Stripe webhooks.
    
    Verifies webhook signature and processes the event.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not sig_header:
        logger.warning("Missing Stripe signature header")
        return HttpResponse("Missing signature", status=400)
    
    try:
        # Verify webhook signature
        event = StripeClient.verify_webhook_signature(
            payload=payload,
            signature=sig_header
        )
        
        if not event:
            logger.warning("Invalid Stripe webhook signature")
            return HttpResponse("Invalid signature", status=400)
        
        # Process the event
        success = process_stripe_webhook(event)
        
        if success:
            return HttpResponse("Webhook processed successfully", status=200)
        else:
            return HttpResponse("Webhook processing failed", status=500)
            
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}", exc_info=True)
        return HttpResponse(f"Error: {str(e)}", status=400)


@csrf_exempt
@require_http_methods(["POST"])
def clerk_webhook(request):
    """
    Handle incoming Clerk webhooks.
    
    Verifies webhook signature using Svix and processes the event.
    """
    import json
    from django.conf import settings
    
    try:
        payload = request.body
        
        # Verify Clerk webhook signature using Svix
        webhook_secret = getattr(settings, 'CLERK_WEBHOOK_SECRET', '')
        
        if webhook_secret:
            from svix.webhooks import Webhook, WebhookVerificationError
            
            # Get the headers needed for verification
            svix_id = request.META.get('HTTP_SVIX_ID', '')
            svix_timestamp = request.META.get('HTTP_SVIX_TIMESTAMP', '')
            svix_signature = request.META.get('HTTP_SVIX_SIGNATURE', '')
            
            if not all([svix_id, svix_timestamp, svix_signature]):
                logger.warning("Missing Svix headers in Clerk webhook")
                return HttpResponse("Missing webhook headers", status=400)
            
            headers = {
                'svix-id': svix_id,
                'svix-timestamp': svix_timestamp,
                'svix-signature': svix_signature,
            }
            
            try:
                wh = Webhook(webhook_secret)
                event = wh.verify(payload, headers)
            except WebhookVerificationError as e:
                logger.error(f"Clerk webhook signature verification failed: {str(e)}")
                return HttpResponse("Invalid signature", status=400)
        else:
            # No webhook secret configured - parse without verification (dev mode)
            logger.warning("CLERK_WEBHOOK_SECRET not configured - skipping signature verification")
            event = json.loads(payload)
        
        # Process the event
        success = process_clerk_webhook(event)
        
        if success:
            return HttpResponse("Webhook processed successfully", status=200)
        else:
            return HttpResponse("Webhook processing failed", status=500)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Clerk webhook")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Error processing Clerk webhook: {str(e)}", exc_info=True)
        return HttpResponse(f"Error: {str(e)}", status=400)
