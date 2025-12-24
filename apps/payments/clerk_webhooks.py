"""
Clerk webhook handlers for user lifecycle events.

This module processes Clerk webhook events for:
- User creation (auto-create Stripe customer)
- User updates (sync email/name to Stripe)
- User deletion (clean up Stripe customer and subscriptions)
"""
import logging
import time
from django.db import transaction

from apps.payments.models import StripeCustomer, WebhookLog
from apps.subscriptions.models import Subscription
from apps.authentication.models import User

logger = logging.getLogger(__name__)


def log_webhook_event(event_type, event_id, payload, processed=False, error_message=''):
    """
    Log webhook event to database for debugging and audit trail.
    
    Args:
        event_type: Type of webhook event (e.g., 'user.created')
        event_id: Unique event ID from Clerk
        payload: Full event payload
        processed: Whether event was successfully processed
        error_message: Error message if processing failed
    """
    try:
        WebhookLog.objects.create(
            source='clerk',
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            processed=processed,
            error_message=error_message
        )
    except Exception as e:
        logger.error(f"Failed to log webhook event {event_id}: {str(e)}")


@transaction.atomic
def handle_user_created(event):
    """
    Handle user.created event from Clerk.
    
    Automatically creates a Stripe customer for the new user.
    For staff members, also links the user to their StaffMember record.
    This ensures every user has a Stripe customer record ready
    for future subscription creation.
    """
    start_time = time.time()
    user_data = event['data']
    event_id = event.get('id', user_data['id'])
    
    try:
        logger.info(f"Processing user.created: {user_data['id']}")
        
        # Extract email from Clerk data
        email_addresses = user_data.get('email_addresses', [])
        primary_email = next(
            (email['email_address'] for email in email_addresses 
             if email.get('id') == user_data.get('primary_email_address_id')),
            email_addresses[0]['email_address'] if email_addresses else None
        )
        
        # Check if this is a staff signup (from invitation)
        public_metadata = user_data.get('public_metadata', {})
        is_staff = public_metadata.get('role') == 'staff'
        
        # Get or create the user
        try:
            user = User.objects.get(clerk_user_id=user_data['id'])
            logger.info(f"Found existing user for clerk_user_id: {user_data['id']}")
        except User.DoesNotExist:
            # User doesn't exist - create them
            # This happens for staff signups via magic link
            logger.info(f"Creating new user for clerk_user_id: {user_data['id']}")
            
            user = User.objects.create(
                clerk_user_id=user_data['id'],
                email=primary_email or '',
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                role='staff' if is_staff else 'customer',
                email_verified=True,
                is_active=True
            )
        
        # Handle staff linking if this is a staff signup
        if is_staff:
            from apps.staff.services import handle_staff_signup
            staff_linked = handle_staff_signup(user_data)
            if staff_linked:
                logger.info(f"Staff member linked for user {user.email}")
            else:
                logger.warning(f"Failed to link staff member for user {user.email}")
        
        # Check if Stripe customer already exists
        if hasattr(user, 'stripe_customer'):
            logger.info(f"Stripe customer already exists for user {user.email}")
            log_webhook_event('user.created', event_id, event, True)
            return True
        
        # Create Stripe customer
        try:
            import stripe
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            stripe_customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    'clerk_user_id': user.clerk_user_id,
                    'created_via': 'clerk_webhook'
                }
            )
            
            # Save to database
            StripeCustomer.objects.create(
                user=user,
                stripe_customer_id=stripe_customer.id,
                email=user.email,
                metadata=stripe_customer.get('metadata', {})
            )
            
            processing_time = time.time() - start_time
            log_webhook_event('user.created', event_id, event, True)
            logger.info(f"Created Stripe customer {stripe_customer.id} for {user.email} in {processing_time:.2f}s")
            
        except Exception as e:
            error_msg = f"Failed to create Stripe customer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            log_webhook_event('user.created', event_id, event, False, error_msg)
            raise
            
    except Exception as e:
        error_msg = f"Error processing user.created: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('user.created', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_user_updated(event):
    """
    Handle user.updated event from Clerk.
    
    Syncs user email and name changes to Stripe customer record.
    """
    start_time = time.time()
    user_data = event['data']
    event_id = event.get('id', user_data['id'])
    
    try:
        logger.info(f"Processing user.updated: {user_data['id']}")
        
        # Get user
        try:
            user = User.objects.select_related('stripe_customer').get(
                clerk_user_id=user_data['id']
            )
        except User.DoesNotExist:
            error_msg = f"User not found for clerk_user_id: {user_data['id']}"
            logger.warning(error_msg)
            log_webhook_event('user.updated', event_id, event, False, error_msg)
            return
        
        # Get or create Stripe customer
        if not hasattr(user, 'stripe_customer'):
            logger.warning(f"No Stripe customer for user {user.email}, creating one")
            # Trigger user.created logic
            handle_user_created(event)
            return
        
        # Update Stripe customer
        try:
            import stripe
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            stripe.Customer.modify(
                user.stripe_customer.stripe_customer_id,
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip()
            )
            
            # Update local record
            user.stripe_customer.email = user.email
            user.stripe_customer.save(update_fields=['email'])
            
            processing_time = time.time() - start_time
            log_webhook_event('user.updated', event_id, event, True)
            logger.info(f"Updated Stripe customer for {user.email} in {processing_time:.2f}s")
            
        except Exception as e:
            error_msg = f"Failed to update Stripe customer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            log_webhook_event('user.updated', event_id, event, False, error_msg)
            # Don't raise - this is not critical
            
    except Exception as e:
        error_msg = f"Error processing user.updated: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('user.updated', event_id, event, False, error_msg)


@transaction.atomic
def handle_user_deleted(event):
    """
    Handle user.deleted event from Clerk.
    
    Cancels all active subscriptions and archives Stripe customer.
    Note: We don't delete the Stripe customer to preserve payment history.
    """
    start_time = time.time()
    user_data = event['data']
    event_id = event.get('id', user_data.get('id', 'unknown'))
    clerk_user_id = user_data.get('id')
    
    try:
        logger.info(f"Processing user.deleted: {clerk_user_id}")
        
        # Find all active subscriptions for this user
        active_subscriptions = Subscription.objects.filter(
            user__clerk_user_id=clerk_user_id,
            status='active'
        )
        
        if not active_subscriptions.exists():
            logger.info(f"No active subscriptions for deleted user {clerk_user_id}")
            log_webhook_event('user.deleted', event_id, event, True)
            return
        
        # Cancel all subscriptions in Stripe
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        canceled_count = 0
        for subscription in active_subscriptions:
            try:
                # Cancel immediately in Stripe
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                
                # Update local record
                subscription.status = 'canceled'
                subscription.is_current = False
                from django.utils import timezone
                subscription.cancelled_at = timezone.now()
                subscription.save()
                
                canceled_count += 1
                logger.info(f"Canceled subscription {subscription.stripe_subscription_id}")
                
            except Exception as e:
                logger.error(f"Failed to cancel subscription {subscription.id}: {str(e)}")
        
        processing_time = time.time() - start_time
        log_webhook_event('user.deleted', event_id, event, True)
        logger.info(f"Canceled {canceled_count} subscriptions for deleted user in {processing_time:.2f}s")
        
    except Exception as e:
        error_msg = f"Error processing user.deleted: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('user.deleted', event_id, event, False, error_msg)
        raise


# Event handler mapping
CLERK_EVENT_HANDLERS = {
    'user.created': handle_user_created,
    'user.updated': handle_user_updated,
    'user.deleted': handle_user_deleted,
}


def process_clerk_webhook(event):
    """
    Main entry point for processing Clerk webhooks.
    
    Args:
        event: Validated Clerk event object
        
    Returns:
        bool: True if processed successfully, False otherwise
    """
    event_type = event.get('type')
    event_id = event.get('id', event.get('data', {}).get('id', 'unknown'))
    
    logger.info(f"Received Clerk webhook: {event_type} ({event_id})")
    
    # Check if event already processed (idempotency)
    if WebhookLog.objects.filter(event_id=event_id, processed=True).exists():
        logger.info(f"Event {event_id} already processed, skipping")
        return True
    
    # Get handler for event type
    handler = CLERK_EVENT_HANDLERS.get(event_type)
    
    if handler:
        try:
            handler(event)
            return True
        except Exception as e:
            logger.error(f"Failed to process event {event_id}: {str(e)}")
            return False
    else:
        logger.info(f"No handler for event type: {event_type}")
        log_webhook_event(event_type, event_id, event, True, 'No handler implemented')
        return True
