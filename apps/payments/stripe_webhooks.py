"""
Stripe webhook handlers for subscription events.

This module processes Stripe webhook events for:
- Subscription lifecycle (created, updated, deleted)
- Payment events (succeeded, failed)
- Customer updates
- Checkout session completion
"""
import logging
import time
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from apps.payments.models import StripeCustomer, WebhookLog
from apps.subscriptions.models import Subscription, SubscriptionPlan, SubscriptionHistory, Payment
from apps.authentication.models import User

logger = logging.getLogger(__name__)


def log_webhook_event(event_type, event_id, payload, processed=False, error_message=''):
    """
    Log webhook event to database for debugging and audit trail.
    
    Args:
        event_type: Type of webhook event (e.g., 'customer.subscription.created')
        event_id: Unique event ID from Stripe
        payload: Full event payload
        processed: Whether event was successfully processed
        error_message: Error message if processing failed
    """
    try:
        WebhookLog.objects.create(
            source='stripe',
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            processed=processed,
            error_message=error_message
        )
    except Exception as e:
        logger.error(f"Failed to log webhook event {event_id}: {str(e)}")


def get_user_from_customer_id(customer_id):
    """Get user from Stripe customer ID."""
    try:
        stripe_customer = StripeCustomer.objects.select_related('user').get(
            stripe_customer_id=customer_id
        )
        return stripe_customer.user
    except StripeCustomer.DoesNotExist:
        logger.error(f"StripeCustomer not found for customer_id: {customer_id}")
        return None


def get_plan_from_price_id(price_id):
    """Get SubscriptionPlan from Stripe price ID."""
    try:
        return SubscriptionPlan.objects.get(stripe_price_id=price_id)
    except SubscriptionPlan.DoesNotExist:
        logger.error(f"SubscriptionPlan not found for price_id: {price_id}")
        return None


@transaction.atomic
def handle_checkout_session_completed(event):
    """
    Handle checkout.session.completed event.
    
    This creates the initial subscription record when user completes payment.
    The subscription.created event will provide more details.
    """
    start_time = time.time()
    session = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing checkout.session.completed: {session['id']}")
        
        # Extract metadata
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        
        if not customer_id or not subscription_id:
            error_msg = "Missing customer_id or subscription_id in checkout session"
            logger.warning(error_msg)
            log_webhook_event('checkout.session.completed', event_id, event, False, error_msg)
            return
        
        # Log successful processing
        processing_time = time.time() - start_time
        log_webhook_event('checkout.session.completed', event_id, event, True)
        logger.info(f"Checkout session completed for subscription: {subscription_id} in {processing_time:.2f}s")
        
    except Exception as e:
        error_msg = f"Error processing checkout.session.completed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('checkout.session.completed', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_subscription_created(event):
    """
    Handle customer.subscription.created event.
    
    Creates a new Subscription record and handles upgrade logic if user
    already has an active subscription.
    """
    start_time = time.time()
    stripe_sub = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing subscription.created: {stripe_sub['id']}")
        
        # Get user and plan
        customer_id = stripe_sub['customer']
        user = get_user_from_customer_id(customer_id)
        if not user:
            raise ValueError(f"User not found for customer: {customer_id}")
        
        # Get price ID from line items
        price_id = stripe_sub['items']['data'][0]['price']['id']
        plan = get_plan_from_price_id(price_id)
        if not plan:
            raise ValueError(f"Plan not found for price: {price_id}")
        
        # Check if user has current subscription (upgrade scenario)
        current_sub = Subscription.objects.filter(
            user=user,
            is_current=True,
            status='active'
        ).first()
        
        if current_sub and plan.amount > current_sub.plan.amount:
            # This is an upgrade - mark old subscription as non-current
            current_sub.is_current = False
            current_sub.cancel_at_period_end = True
            current_sub.save()
            logger.info(f"Marked old subscription {current_sub.id} as non-current for upgrade")
            
            # Log upgrade in history
            SubscriptionHistory.objects.create(
                subscription=current_sub,
                action='upgraded',
                old_plan=current_sub.plan,
                new_plan=plan,
                reason='User upgraded to higher tier'
            )
        
        # Create new subscription
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            stripe_subscription_id=stripe_sub['id'],
            stripe_customer_id=customer_id,
            status=stripe_sub['status'],
            is_current=True,
            current_period_start=datetime.fromtimestamp(stripe_sub['current_period_start'], tz=timezone.utc),
            current_period_end=datetime.fromtimestamp(stripe_sub['current_period_end'], tz=timezone.utc),
            cancel_at_period_end=stripe_sub.get('cancel_at_period_end', False)
        )
        
        # Log creation in history
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='created',
            new_plan=plan,
            reason='Subscription created via Stripe checkout'
        )
        
        processing_time = time.time() - start_time
        log_webhook_event('customer.subscription.created', event_id, event, True)
        logger.info(f"Created subscription {subscription.id} for {user.email} in {processing_time:.2f}s")
        
    except Exception as e:
        error_msg = f"Error processing subscription.created: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('customer.subscription.created', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_subscription_updated(event):
    """
    Handle customer.subscription.updated event.
    
    Updates subscription status, billing dates, and handles cancellations.
    """
    start_time = time.time()
    stripe_sub = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing subscription.updated: {stripe_sub['id']}")
        
        subscription = Subscription.objects.select_related('plan').get(
            stripe_subscription_id=stripe_sub['id']
        )
        
        # Update subscription fields
        old_status = subscription.status
        subscription.status = stripe_sub['status']
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_sub['current_period_end'],
            tz=timezone.utc
        )
        subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
        
        if stripe_sub['status'] == 'canceled' and not subscription.cancelled_at:
            subscription.cancelled_at = timezone.now()
        
        subscription.save()
        
        # Log status change if it changed
        if old_status != stripe_sub['status']:
            logger.info(f"Subscription {subscription.id} status changed: {old_status} -> {stripe_sub['status']}")
            
            # If subscription became inactive, deactivate shops
            if stripe_sub['status'] in ['canceled', 'unpaid']:
                try:
                    client = subscription.user.client_profile
                    deactivated_count = client.shops.filter(is_active=True).update(is_active=False)
                    logger.info(f"Deactivated {deactivated_count} shops for expired subscription")
                except Exception as e:
                    logger.error(f"Error deactivating shops: {str(e)}")
        
        processing_time = time.time() - start_time
        log_webhook_event('customer.subscription.updated', event_id, event, True)
        logger.info(f"Updated subscription {subscription.id} in {processing_time:.2f}s")
        
    except Subscription.DoesNotExist:
        error_msg = f"Subscription not found: {stripe_sub['id']}"
        logger.warning(error_msg)
        log_webhook_event('customer.subscription.updated', event_id, event, False, error_msg)
    except Exception as e:
        error_msg = f"Error processing subscription.updated: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('customer.subscription.updated', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_subscription_deleted(event):
    """
    Handle customer.subscription.deleted event.
    
    Marks subscription as canceled and deactivates all shops for the client.
    """
    start_time = time.time()
    stripe_sub = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing subscription.deleted: {stripe_sub['id']}")
        
        subscription = Subscription.objects.select_related('user__client_profile').get(
            stripe_subscription_id=stripe_sub['id']
        )
        
        # Mark subscription as canceled
        subscription.status = 'canceled'
        subscription.is_current = False
        subscription.cancelled_at = timezone.now()
        subscription.save()
        
        # Deactivate all shops
        try:
            client = subscription.user.client_profile
            deactivated_count = client.shops.update(is_active=False)
            logger.info(f"Deactivated {deactivated_count} shops for canceled subscription")
        except Exception as e:
            logger.error(f"Error deactivating shops: {str(e)}")
        
        # Log cancellation
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='cancelled',
            reason='Subscription canceled/expired in Stripe'
        )
        
        processing_time = time.time() - start_time
        log_webhook_event('customer.subscription.deleted', event_id, event, True)
        logger.info(f"Deleted subscription {subscription.id} in {processing_time:.2f}s")
        
    except Subscription.DoesNotExist:
        error_msg = f"Subscription not found: {stripe_sub['id']}"
        logger.warning(error_msg)
        log_webhook_event('customer.subscription.deleted', event_id, event, False, error_msg)
    except Exception as e:
        error_msg = f"Error processing subscription.deleted: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('customer.subscription.deleted', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_invoice_payment_succeeded(event):
    """
    Handle invoice.payment_succeeded event.
    
    Records successful payment in Payment model.
    """
    start_time = time.time()
    invoice = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing invoice.payment_succeeded: {invoice['id']}")
        
        # Get subscription
        if not invoice.get('subscription'):
            logger.info("Invoice not related to subscription, skipping")
            log_webhook_event('invoice.payment_succeeded', event_id, event, True)
            return
        
        subscription = Subscription.objects.get(
            stripe_subscription_id=invoice['subscription']
        )
        
        # Create payment record
        payment = Payment.objects.create(
            subscription=subscription,
            amount=invoice['amount_paid'] / 100,  # Convert from cents
            payment_method=invoice.get('charge', {}).get('payment_method_details', {}).get('type', 'card'),
            transaction_id=invoice['payment_intent'] or invoice['id'],
            stripe_payment_intent_id=invoice.get('payment_intent', ''),
            stripe_invoice_id=invoice['id'],
            status='succeeded',
            payment_date=datetime.fromtimestamp(invoice['status_transitions']['paid_at'], tz=timezone.utc),
            metadata=invoice
        )
        
        # Update subscription's latest invoice
        subscription.stripe_latest_invoice = invoice['id']
        subscription.save(update_fields=['stripe_latest_invoice'])
        
        processing_time = time.time() - start_time
        log_webhook_event('invoice.payment_succeeded', event_id, event, True)
        logger.info(f"Recorded payment {payment.id} for invoice {invoice['id']} in {processing_time:.2f}s")
        
    except Subscription.DoesNotExist:
        error_msg = f"Subscription not found for invoice: {invoice['id']}"
        logger.warning(error_msg)
        log_webhook_event('invoice.payment_succeeded', event_id, event, False, error_msg)
    except Exception as e:
        error_msg = f"Error processing invoice.payment_succeeded: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('invoice.payment_succeeded', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_invoice_payment_failed(event):
    """
    Handle invoice.payment_failed event.
    
    Marks subscription as past_due and logs failed payment.
    """
    start_time = time.time()
    invoice = event['data']['object']
    event_id = event['id']
    
    try:
        logger.warning(f"Processing invoice.payment_failed: {invoice['id']}")
        
        if not invoice.get('subscription'):
            logger.info("Invoice not related to subscription, skipping")
            log_webhook_event('invoice.payment_failed', event_id, event, True)
            return
        
        subscription = Subscription.objects.get(
            stripe_subscription_id=invoice['subscription']
        )
        
        # Update subscription status
        subscription.status = 'past_due'
        subscription.save(update_fields=['status'])
        
        # Create failed payment record
        Payment.objects.create(
            subscription=subscription,
            amount=invoice['amount_due'] / 100,
            payment_method='unknown',
            transaction_id=invoice['id'],
            stripe_invoice_id=invoice['id'],
            status='failed',
            payment_date=timezone.now(),
            metadata=invoice
        )
        
        # TODO: Send notification to user about payment failure
        
        processing_time = time.time() - start_time
        log_webhook_event('invoice.payment_failed', event_id, event, True)
        logger.warning(f"Payment failed for subscription {subscription.id} in {processing_time:.2f}s")
        
    except Subscription.DoesNotExist:
        error_msg = f"Subscription not found for invoice: {invoice['id']}"
        logger.warning(error_msg)
        log_webhook_event('invoice.payment_failed', event_id, event, False, error_msg)
    except Exception as e:
        error_msg = f"Error processing invoice.payment_failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('invoice.payment_failed', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_payment_intent_succeeded(event):
    """
    Handle payment_intent.succeeded event.
    
    For booking advance payments - confirms the booking when payment completes.
    """
    start_time = time.time()
    payment_intent = event['data']['object']
    event_id = event['id']
    
    try:
        # Check if this is a booking payment
        metadata = payment_intent.get('metadata', {})
        if metadata.get('type') != 'advance_deposit':
            logger.info(f"Payment intent {payment_intent['id']} is not a booking deposit, skipping")
            log_webhook_event('payment_intent.succeeded', event_id, event, True, 'Not a booking deposit')
            return
        
        logger.info(f"Processing payment_intent.succeeded for booking deposit: {payment_intent['id']}")
        
        # Confirm booking payment
        from apps.payments.booking_payment_service import booking_payment_service
        result = booking_payment_service.confirm_booking_payment(payment_intent['id'])
        
        if result['success']:
            processing_time = time.time() - start_time
            log_webhook_event('payment_intent.succeeded', event_id, event, True)
            logger.info(f"Confirmed booking {result.get('booking_id')} in {processing_time:.2f}s")
        else:
            log_webhook_event('payment_intent.succeeded', event_id, event, False, result.get('error', 'Unknown error'))
            
    except Exception as e:
        error_msg = f"Error processing payment_intent.succeeded: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('payment_intent.succeeded', event_id, event, False, error_msg)
        raise


@transaction.atomic
def handle_payment_intent_payment_failed(event):
    """
    Handle payment_intent.payment_failed event.
    
    Logs failed booking payment attempts.
    """
    payment_intent = event['data']['object']
    event_id = event['id']
    
    metadata = payment_intent.get('metadata', {})
    if metadata.get('type') != 'advance_deposit':
        log_webhook_event('payment_intent.payment_failed', event_id, event, True, 'Not a booking deposit')
        return
    
    logger.warning(f"Booking payment failed: {payment_intent['id']}")
    
    # Update BookingPayment status
    try:
        from apps.payments.models import BookingPayment
        from apps.core.utils.constants import BOOKING_PAYMENT_FAILED
        
        booking_payment = BookingPayment.objects.get(
            stripe_payment_intent_id=payment_intent['id']
        )
        booking_payment.status = BOOKING_PAYMENT_FAILED
        booking_payment.save(update_fields=['status'])
        
        booking_payment.booking.payment_status = BOOKING_PAYMENT_FAILED
        booking_payment.booking.save(update_fields=['payment_status'])
        
        log_webhook_event('payment_intent.payment_failed', event_id, event, True)
        
    except BookingPayment.DoesNotExist:
        log_webhook_event('payment_intent.payment_failed', event_id, event, False, 'BookingPayment not found')


@transaction.atomic
def handle_account_updated(event):
    """
    Handle account.updated event for Connect accounts.
    
    Updates local ConnectedAccount record when owner completes onboarding.
    """
    start_time = time.time()
    account = event['data']['object']
    event_id = event['id']
    
    try:
        logger.info(f"Processing account.updated: {account['id']}")
        
        from apps.payments.models import ConnectedAccount
        
        try:
            connected_account = ConnectedAccount.objects.get(
                stripe_account_id=account['id']
            )
        except ConnectedAccount.DoesNotExist:
            logger.warning(f"ConnectedAccount not found for {account['id']}")
            log_webhook_event('account.updated', event_id, event, False, 'Account not found')
            return
        
        # Update account status
        connected_account.charges_enabled = account.get('charges_enabled', False)
        connected_account.payouts_enabled = account.get('payouts_enabled', False)
        connected_account.details_submitted = account.get('details_submitted', False)
        
        # Check if onboarding is complete
        if connected_account.charges_enabled and connected_account.details_submitted:
            connected_account.onboarding_complete = True
        
        connected_account.business_type = account.get('business_type', '')
        connected_account.save()
        
        processing_time = time.time() - start_time
        log_webhook_event('account.updated', event_id, event, True)
        logger.info(f"Updated ConnectedAccount {account['id']} in {processing_time:.2f}s")
        
    except Exception as e:
        error_msg = f"Error processing account.updated: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_webhook_event('account.updated', event_id, event, False, error_msg)
        raise


# Event handler mapping
STRIPE_EVENT_HANDLERS = {
    'checkout.session.completed': handle_checkout_session_completed,
    'customer.subscription.created': handle_subscription_created,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_succeeded': handle_invoice_payment_succeeded,
    'invoice.payment_failed': handle_invoice_payment_failed,
    # Booking payment events
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_payment_failed,
    # Connect account events
    'account.updated': handle_account_updated,
}


def process_stripe_webhook(event):
    """
    Main entry point for processing Stripe webhooks.
    
    Args:
        event: Validated Stripe event object
        
    Returns:
        bool: True if processed successfully, False otherwise
    """
    event_type = event['type']
    event_id = event['id']
    
    logger.info(f"Received Stripe webhook: {event_type} ({event_id})")
    
    # Check if event already processed (idempotency)
    if WebhookLog.objects.filter(event_id=event_id, processed=True).exists():
        logger.info(f"Event {event_id} already processed, skipping")
        return True
    
    # Get handler for event type
    logger.info(f"Looking for handler for event_type: '{event_type}'")
    logger.info(f"Available handlers: {list(STRIPE_EVENT_HANDLERS.keys())}")
    handler = STRIPE_EVENT_HANDLERS.get(event_type)
    
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
