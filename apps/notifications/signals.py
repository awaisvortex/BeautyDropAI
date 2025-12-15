"""
Django signals for automatic notification triggering.
Handles booking events, staff changes, and shop holidays.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Store original values for comparison in post_save
_booking_originals = {}


@receiver(pre_save, sender='bookings.Booking')
def booking_pre_save(sender, instance, **kwargs):
    """
    Capture original booking state before save.
    Used to detect staff changes and status changes.
    """
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            _booking_originals[instance.pk] = {
                'status': original.status,
                'staff_member_id': original.staff_member_id,
                'booking_datetime': original.booking_datetime,
            }
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='bookings.Booking')
def booking_post_save(sender, instance, created, **kwargs):
    """
    Handle booking save events and trigger appropriate notifications.
    
    Triggers:
    - Booking confirmation on creation with confirmed status
    - Staff assignment notification on staff change
    - Reschedule notification on datetime change
    - Cancellation notification on status change to cancelled
    """
    from apps.notifications.tasks import (
        send_booking_confirmation_task,
        send_booking_cancellation_task,
        send_staff_assignment_task,
    )
    
    booking_id = str(instance.id)
    
    if created:
        # New booking - send confirmation if confirmed or pending
        if instance.status in ['confirmed', 'pending']:
            try:
                send_booking_confirmation_task.delay(booking_id)
                logger.info(f"Queued confirmation email for new booking {booking_id}")
            except Exception as e:
                logger.error(f"Failed to queue confirmation for booking {booking_id}: {e}")
        return
    
    # Existing booking - check for changes
    original = _booking_originals.pop(instance.pk, None)
    if not original:
        return
    
    # Check for cancellation
    if instance.status == 'cancelled' and original['status'] != 'cancelled':
        try:
            # Determine who cancelled based on context
            # This is a simplified version - in reality you'd track this
            cancelled_by = 'customer'  # Default assumption
            send_booking_cancellation_task.delay(booking_id, cancelled_by)
            logger.info(f"Queued cancellation email for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue cancellation for booking {booking_id}: {e}")
        return
    
    # Check for staff member change
    if original['staff_member_id'] != instance.staff_member_id:
        try:
            old_staff_id = str(original['staff_member_id']) if original['staff_member_id'] else None
            new_staff_id = str(instance.staff_member_id) if instance.staff_member_id else None
            send_staff_assignment_task.delay(booking_id, old_staff_id, new_staff_id)
            logger.info(f"Queued staff assignment email for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue staff assignment for booking {booking_id}: {e}")
    
    # Check for reschedule (datetime change)
    if original['booking_datetime'] != instance.booking_datetime:
        # For now, we'll send a confirmation with the new time
        # In a full implementation, you'd have a specific reschedule email
        try:
            send_booking_confirmation_task.delay(booking_id)
            logger.info(f"Queued reschedule notification for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue reschedule for booking {booking_id}: {e}")


@receiver(post_save, sender='schedules.Holiday')
def shop_holiday_created(sender, instance, created, **kwargs):
    """
    Handle shop holiday creation and notify affected customers.
    """
    if not created:
        return
    
    from apps.notifications.tasks import send_shop_holiday_notification_task
    
    try:
        shop_id = str(instance.shop_id)
        holiday_date = instance.date.isoformat()
        send_shop_holiday_notification_task.delay(shop_id, holiday_date)
        logger.info(f"Queued holiday notifications for shop {shop_id} on {holiday_date}")
    except Exception as e:
        logger.error(f"Failed to queue holiday notifications: {e}")


@receiver(post_save, sender='authentication.User')
def create_notification_preferences(sender, instance, created, **kwargs):
    """
    Create default notification preferences for new users.
    """
    if created:
        from apps.notifications.models import NotificationPreference
        
        try:
            NotificationPreference.objects.create(user=instance)
            logger.debug(f"Created notification preferences for user {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create notification preferences for {instance.email}: {e}")
