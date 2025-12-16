"""
Celery tasks for Google Calendar sync operations.
These run asynchronously to avoid blocking API responses.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_booking_task(self, booking_id: str):
    """
    Sync a single booking to the customer's Google Calendar.
    Called when a booking is confirmed.
    
    Args:
        booking_id: UUID of the booking to sync
    """
    from apps.bookings.models import Booking
    from apps.calendars.models import CalendarIntegration, CalendarEvent
    from apps.calendars.google_calendar_service import GoogleCalendarService
    from apps.authentication.services.clerk_service import clerk_service
    
    try:
        booking = Booking.objects.select_related(
            'customer__user', 'service', 'shop', 'staff_member__user'
        ).get(id=booking_id)
        
        # Get customer's calendar integration
        try:
            integration = CalendarIntegration.objects.get(user=booking.customer.user)
        except CalendarIntegration.DoesNotExist:
            logger.debug(f"No calendar integration for booking {booking_id}")
            return
        
        if not integration.is_connected or not integration.is_sync_enabled:
            logger.debug(f"Calendar sync disabled for user {booking.customer.user.email}")
            return
        
        # Fetch fresh Google OAuth token from Clerk
        token_data = clerk_service.get_google_oauth_token(booking.customer.user.clerk_user_id)
        if not token_data or not token_data.get('token'):
            logger.warning(f"Could not get Google token from Clerk for user {booking.customer.user.email}")
            return
        
        # Initialize Google Calendar service with fresh token
        calendar_service = GoogleCalendarService(token_data['token'])
        
        # Check if event already exists
        calendar_event, created = CalendarEvent.objects.get_or_create(
            booking=booking,
            integration=integration
        )
        
        try:
            if calendar_event.google_event_id:
                # Update existing event
                calendar_service.update_booking_event(
                    calendar_event.google_event_id,
                    booking,
                    integration.google_calendar_id
                )
            else:
                # Create new event
                event_id = calendar_service.create_booking_event(
                    booking,
                    integration.google_calendar_id
                )
                calendar_event.google_event_id = event_id
            
            calendar_event.is_synced = True
            calendar_event.last_synced_at = timezone.now()
            calendar_event.sync_error = ''
            calendar_event.save()
            
            # Update integration last sync time
            integration.last_sync_at = timezone.now()
            integration.save(update_fields=['last_sync_at'])
            
            logger.info(f"Successfully synced booking {booking_id} to Google Calendar")
            
        except Exception as e:
            calendar_event.sync_error = str(e)
            calendar_event.is_synced = False
            calendar_event.save()
            raise
    
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found for calendar sync")
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def delete_calendar_event_task(self, booking_id: str):
    """
    Delete a calendar event when a booking is cancelled.
    
    Args:
        booking_id: UUID of the cancelled booking
    """
    from apps.calendars.models import CalendarEvent
    from apps.calendars.google_calendar_service import GoogleCalendarService
    from apps.authentication.services.clerk_service import clerk_service
    
    try:
        calendar_event = CalendarEvent.objects.select_related(
            'integration__user'
        ).get(booking_id=booking_id)
        
        if not calendar_event.google_event_id:
            logger.debug(f"No Google event ID for booking {booking_id}")
            return
        
        integration = calendar_event.integration
        
        # Fetch fresh Google OAuth token from Clerk
        token_data = clerk_service.get_google_oauth_token(integration.user.clerk_user_id)
        if not token_data or not token_data.get('token'):
            logger.warning(f"Could not get Google token from Clerk for user {integration.user.email}")
            # Still delete local record
            calendar_event.delete()
            return
        
        calendar_service = GoogleCalendarService(token_data['token'])
        
        calendar_service.delete_booking_event(
            calendar_event.google_event_id,
            integration.google_calendar_id
        )
        
        # Delete the calendar event record
        calendar_event.delete()
        
        logger.info(f"Deleted calendar event for booking {booking_id}")
    
    except CalendarEvent.DoesNotExist:
        logger.debug(f"No calendar event for booking {booking_id}")
    except Exception as e:
        logger.error(f"Failed to delete calendar event for booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_bookings_task(self, user_id: str):
    """
    Sync all future confirmed bookings for a user.
    Called on initial calendar connection or manual sync.
    
    Args:
        user_id: UUID of the user
    """
    from django.utils import timezone
    from apps.authentication.models import User
    from apps.bookings.models import Booking
    from apps.customers.models import Customer
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get customer profile
        try:
            customer = Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            logger.debug(f"User {user_id} is not a customer")
            return
        
        # Get all future confirmed bookings
        future_bookings = Booking.objects.filter(
            customer=customer,
            status='confirmed',
            booking_datetime__gte=timezone.now()
        ).values_list('id', flat=True)
        
        # Queue individual sync tasks
        for booking_id in future_bookings:
            sync_booking_task.delay(str(booking_id))
        
        logger.info(f"Queued {len(future_bookings)} bookings for sync for user {user_id}")
    
    except Exception as e:
        logger.error(f"Failed to sync all bookings for user {user_id}: {e}")
        raise self.retry(exc=e)
