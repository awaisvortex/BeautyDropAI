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
    
    Args:
        booking_id: UUID of the booking to check/cancel
    """
    from apps.bookings.models import Booking
    
    try:
        booking = Booking.objects.get(id=booking_id)
        
        # Check if booking is still pending
        if booking.status != 'pending':
            logger.info(f"Booking {booking_id} already processed (status: {booking.status}). Skipping cancellation.")
            return
        
        # Check payment status
        if hasattr(booking, 'payment_record') and booking.payment_record:
            payment_status = booking.payment_record.status
            if payment_status in ['succeeded', 'processing']:
                logger.info(f"Booking {booking_id} payment {payment_status}. Skipping cancellation.")
                return
        
        # Cancel the booking
        booking.status = 'cancelled'
        booking.cancellation_reason = 'Payment not completed within 15 minutes'
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])
        
        logger.info(f"Successfully cancelled unpaid booking {booking_id} (Payment timeout)")
        
        # TODO: Optionally send notification to customer about cancellation
        
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found for cancellation")
    except Exception as e:
        logger.error(f"Error cancelling unpaid booking {booking_id}: {str(e)}")
