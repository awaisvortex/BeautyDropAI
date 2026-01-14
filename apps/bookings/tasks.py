"""
Celery tasks for bookings app.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='bookings.cancel_unpaid_booking')
def cancel_unpaid_booking(booking_id: str):
    """
    Cancel a booking if payment wasn't completed within timeout period.
    
    This task is scheduled when a pending booking with payment is created.
    It runs after 15 minutes and cancels the booking if still pending.
    
    Also:
    - Cancels the Stripe PaymentIntent to prevent late payments
    - Sends email notification to customer
    - Sends push notification to customer
    
    Args:
        booking_id: UUID of the booking to check/cancel
    """
    from apps.bookings.models import Booking
    from apps.payments.models import BookingPayment
    from apps.payments.stripe_connect import stripe_connect_client
    
    try:
        booking = Booking.objects.select_related(
            'customer__user', 'shop', 'service', 'deal'
        ).get(id=booking_id)
        
        # Check if booking is still pending
        if booking.status != 'pending':
            logger.info(f"Booking {booking_id} already processed (status: {booking.status}). Skipping cancellation.")
            return
        
        # Check payment status - use advance_payment related name
        try:
            payment = booking.advance_payment
            if payment.status in ['paid', 'succeeded', 'processing']:
                logger.info(f"Booking {booking_id} payment {payment.status}. Skipping cancellation.")
                return
            
            # Cancel the Stripe PaymentIntent to prevent late payments
            if payment.stripe_payment_intent_id:
                try:
                    stripe_connect_client.cancel_payment_intent(payment.stripe_payment_intent_id)
                    logger.info(f"Cancelled PaymentIntent {payment.stripe_payment_intent_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel PaymentIntent: {e}")
        except BookingPayment.DoesNotExist:
            pass  # No payment record, can proceed with cancellation
        
        # Get item name for notification
        if booking.service:
            item_name = booking.service.name
        elif booking.deal:
            item_name = booking.deal.name
        else:
            item_name = "appointment"
        
        # Cancel the booking
        booking.status = 'cancelled'
        booking.cancelled_by = 'system'
        booking.cancellation_reason = 'Payment not completed within 15 minutes'
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=['status', 'cancelled_by', 'cancellation_reason', 'cancelled_at', 'updated_at'])
        
        logger.info(f"Successfully cancelled unpaid booking {booking_id} (Payment timeout)")
        
        # Send notifications to customer
        try:
            customer_user = booking.customer.user
            shop_name = booking.shop.name
            formatted_datetime = booking.booking_datetime.strftime("%B %d, %Y at %I:%M %p")
            
            # Send email notification
            send_booking_cancelled_email.delay(
                user_email=customer_user.email,
                user_name=customer_user.full_name,
                shop_name=shop_name,
                item_name=item_name,
                booking_datetime=formatted_datetime,
                reason='Payment was not completed within the 15-minute window.'
            )
            
            # Send push notification
            send_booking_cancelled_push.delay(
                user_id=str(customer_user.id),
                title='Booking Cancelled',
                body=f'Your booking for {item_name} at {shop_name} was cancelled due to incomplete payment.'
            )
            
        except Exception as e:
            logger.error(f"Failed to send cancellation notifications: {e}")
        
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found for cancellation")
    except Exception as e:
        logger.error(f"Error cancelling unpaid booking {booking_id}: {str(e)}")


@shared_task(name='bookings.send_booking_cancelled_email')
def send_booking_cancelled_email(
    user_email: str,
    user_name: str,
    shop_name: str,
    item_name: str,
    booking_datetime: str,
    reason: str
):
    """Send email notification when booking is cancelled due to payment timeout."""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = f'Booking Cancelled - {shop_name}'
    message = f"""
Hi {user_name},

Your booking for {item_name} at {shop_name} on {booking_datetime} has been cancelled.

Reason: {reason}

If you'd like to book again, please visit the app and complete payment within 15 minutes of booking.

Thank you,
BeautyDrop Team
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info(f"Sent cancellation email to {user_email}")
    except Exception as e:
        logger.error(f"Failed to send cancellation email to {user_email}: {e}")


@shared_task(name='bookings.send_booking_cancelled_push')
def send_booking_cancelled_push(user_id: str, title: str, body: str):
    """Send push notification when booking is cancelled."""
    from apps.authentication.models import User
    from apps.notifications.services.fcm_service import FCMService
    
    try:
        user = User.objects.get(id=user_id)
        FCMService.send_to_user(
            user=user,
            title=title,
            body=body,
            data={'type': 'booking_cancelled'},
            notification_type='booking'
        )
        logger.info(f"Sent cancellation push to user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for push notification")
    except Exception as e:
        logger.error(f"Failed to send cancellation push to user {user_id}: {e}")

