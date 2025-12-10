"""
Django signals for automatic calendar sync.
Listens to booking events and triggers calendar operations.
"""
import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def sync_booking_to_calendar(sender, instance, created, **kwargs):
    """
    Auto-create/update calendar event when booking is confirmed.
    Uses update_fields to detect status changes.
    """
    from apps.calendars.tasks import sync_booking_task
    
    # Only sync confirmed bookings
    if instance.status == 'confirmed':
        # Check if customer has calendar integration
        try:
            from apps.calendars.models import CalendarIntegration
            integration = CalendarIntegration.objects.get(user=instance.customer.user)
            
            if integration.is_connected and integration.is_sync_enabled:
                # Queue async sync task
                sync_booking_task.delay(str(instance.id))
                logger.debug(f"Queued calendar sync for booking {instance.id}")
        except CalendarIntegration.DoesNotExist:
            # User hasn't connected calendar - that's fine
            pass
        except Exception as e:
            # Don't let calendar issues block booking operations
            logger.error(f"Failed to queue calendar sync for booking {instance.id}: {e}")


@receiver(pre_delete, sender=Booking)
def remove_booking_from_calendar(sender, instance, **kwargs):
    """
    Remove calendar event when booking is deleted.
    """
    from apps.calendars.tasks import delete_calendar_event_task
    from apps.calendars.models import CalendarEvent
    
    try:
        # Check if there's a calendar event for this booking
        if CalendarEvent.objects.filter(booking=instance).exists():
            delete_calendar_event_task.delay(str(instance.id))
            logger.debug(f"Queued calendar event deletion for booking {instance.id}")
    except Exception as e:
        # Don't let calendar issues block booking deletion
        logger.error(f"Failed to queue calendar deletion for booking {instance.id}: {e}")
