"""
Booking background tasks.

This module contains Celery tasks for:
- Cleaning up expired pending bookings
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.bookings.models import Booking
from apps.core.utils.constants import BOOKING_STATUS_PENDING

logger = logging.getLogger(__name__)


@shared_task
def cancel_expired_pending_bookings():
    """
    Cancel bookings that have been pending for more than 15 minutes.
    
    This releases the time slot for other customers if the original
    customer abandoned the checkout flow.
    """
    # 15 minute expiration window
    expiration_time = timezone.now() - timedelta(minutes=15)
    
    # Find expired pending bookings
    expired_bookings = Booking.objects.filter(
        status=BOOKING_STATUS_PENDING,
        created_at__lt=expiration_time
    )
    
    count = expired_bookings.count()
    if count == 0:
        return f"No expired pending bookings found."
    
    logger.info(f"Found {count} expired pending bookings to cancel")
    
    cancelled_count = 0
    for booking in expired_bookings:
        try:
            # Mark as cancelled by system
            booking.status = 'cancelled'
            booking.cancelled_by = 'system'
            booking.cancelled_at = timezone.now()
            booking.cancellation_reason = 'Payment timeout - booking abandoned'
            booking.save(update_fields=[
                'status', 'cancelled_by', 'cancelled_at', 'cancellation_reason'
            ])
            
            # Release time slot
            if booking.time_slot:
                booking.time_slot.status = 'available'
                booking.time_slot.save(update_fields=['status'])
                
            cancelled_count += 1
            logger.info(f"Cancelled expired booking {booking.id}")
            
        except Exception as e:
            logger.error(f"Error cancelling booking {booking.id}: {str(e)}")
            
    return f"Successfully cancelled {cancelled_count} expired pending bookings."
