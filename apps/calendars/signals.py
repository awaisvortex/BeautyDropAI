"""
Django signals for automatic calendar sync.
Listens to booking events and triggers calendar operations for all user types.
"""
import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)


def queue_calendar_sync_for_user(user, booking_id: str):
    """
    Queue calendar sync for a user if they have calendar integration enabled.
    """
    from apps.calendars.tasks import sync_booking_for_user_task
    from apps.calendars.models import CalendarIntegration
    
    try:
        integration = CalendarIntegration.objects.get(user=user)
        
        if integration.is_connected and integration.is_sync_enabled:
            sync_booking_for_user_task.delay(str(booking_id), user.clerk_user_id)
            logger.debug(f"Queued calendar sync for booking {booking_id} for user {user.email}")
    except CalendarIntegration.DoesNotExist:
        pass  # User hasn't connected calendar
    except Exception as e:
        logger.error(f"Failed to queue calendar sync for user {user.email}: {e}")


@receiver(post_save, sender=Booking)
def sync_booking_to_calendar(sender, instance, created, **kwargs):
    """
    Auto-create/update calendar event when booking is confirmed.
    Syncs to all relevant users: customer, staff, and shop owner.
    """
    # Only sync confirmed bookings
    if instance.status != 'confirmed':
        return
    
    booking_id = str(instance.id)
    
    # 1. Sync to Customer's calendar
    if instance.customer and instance.customer.user:
        queue_calendar_sync_for_user(instance.customer.user, booking_id)
    
    # 2. Sync to Staff member's calendar (if assigned)
    if instance.staff_member and instance.staff_member.user:
        queue_calendar_sync_for_user(instance.staff_member.user, booking_id)
    
    # 3. Sync to Shop owner's (Client) calendar
    if instance.shop and hasattr(instance.shop, 'client') and instance.shop.client:
        if instance.shop.client.user:
            queue_calendar_sync_for_user(instance.shop.client.user, booking_id)


@receiver(pre_delete, sender=Booking)
def remove_booking_from_calendar(sender, instance, **kwargs):
    """
    Remove calendar event when booking is deleted.
    Removes from all users who have this booking synced.
    """
    from apps.calendars.tasks import delete_calendar_event_task
    from apps.calendars.models import CalendarEvent
    
    try:
        # Delete all calendar events associated with this booking
        calendar_events = CalendarEvent.objects.filter(booking=instance)
        for event in calendar_events:
            if event.google_event_id:
                delete_calendar_event_task.delay(str(instance.id), event.integration.user.clerk_user_id)
                logger.debug(f"Queued calendar event deletion for booking {instance.id} user {event.integration.user.email}")
    except Exception as e:
        logger.error(f"Failed to queue calendar deletion for booking {instance.id}: {e}")
