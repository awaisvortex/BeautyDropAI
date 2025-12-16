"""
Celery tasks for Google Calendar sync operations.
These run asynchronously to avoid blocking API responses.
Supports syncing for all user types: customers, staff, and clients.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_booking_description(booking, user_role: str) -> str:
    """
    Build a formatted description for the calendar event based on user role.
    """
    lines = [
        f"Service: {booking.service.name}",
        f"Shop: {booking.shop.name}",
        f"Price: ${booking.total_price}",
    ]
    
    if user_role == 'customer':
        if booking.staff_member:
            lines.append(f"Staff: {booking.staff_member.name}")
    elif user_role == 'staff':
        if booking.customer:
            if booking.customer.user:
                lines.append(f"Customer: {booking.customer.user.full_name or booking.customer.user.email}")
            else:
                lines.append("Customer: (Unknown)")
    elif user_role == 'client':
        if booking.customer:
            if booking.customer.user:
                lines.append(f"Customer: {booking.customer.user.full_name or booking.customer.user.email}")
            else:
                lines.append("Customer: (Unknown)")
        if booking.staff_member:
            lines.append(f"Staff: {booking.staff_member.name}")
    
    if booking.notes:
        lines.append(f"\nNotes: {booking.notes}")
    
    lines.append(f"\nBooking ID: {booking.id}")
    
    return "\n".join(lines)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_booking_for_user_task(self, booking_id: str, clerk_user_id: str):
    """
    Sync a single booking to a specific user's Google Calendar.
    
    Args:
        booking_id: UUID of the booking to sync
        clerk_user_id: Clerk user ID of the user to sync to
    """
    from apps.bookings.models import Booking
    from apps.authentication.models import User
    from apps.calendars.models import CalendarIntegration, CalendarEvent
    from apps.calendars.google_calendar_service import GoogleCalendarService
    from apps.authentication.services.clerk_service import clerk_service
    
    try:
        booking = Booking.objects.select_related(
            'customer__user', 'service', 'shop__client__user', 'staff_member__user'
        ).get(id=booking_id)
        
        user = User.objects.get(clerk_user_id=clerk_user_id)
        
        # Get user's calendar integration
        try:
            integration = CalendarIntegration.objects.get(user=user)
        except CalendarIntegration.DoesNotExist:
            logger.debug(f"No calendar integration for user {clerk_user_id}")
            return
        
        if not integration.is_connected or not integration.is_sync_enabled:
            logger.debug(f"Calendar sync disabled for user {user.email}")
            return
        
        # Fetch fresh Google OAuth token from Clerk
        token_data = clerk_service.get_google_oauth_token(clerk_user_id)
        if not token_data or not token_data.get('token'):
            logger.warning(f"Could not get Google token from Clerk for user {user.email}")
            return
        
        # Initialize Google Calendar service with fresh token
        calendar_service = GoogleCalendarService(token_data['token'])
        
        # Determine user role for event description
        user_role = user.role
        
        # Check if event already exists for this user
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
            
            logger.info(f"Successfully synced booking {booking_id} to Google Calendar for user {user.email}")
            
        except Exception as e:
            calendar_event.sync_error = str(e)
            calendar_event.is_synced = False
            calendar_event.save()
            raise
    
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found for calendar sync")
    except User.DoesNotExist:
        logger.warning(f"User {clerk_user_id} not found for calendar sync")
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id} for user {clerk_user_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def delete_calendar_event_task(self, booking_id: str, clerk_user_id: str = None):
    """
    Delete a calendar event when a booking is cancelled.
    If clerk_user_id is provided, only delete for that user.
    Otherwise, delete for all users who have this booking synced.
    
    Args:
        booking_id: UUID of the cancelled booking
        clerk_user_id: Optional - specific user to delete event for
    """
    from apps.calendars.models import CalendarEvent
    from apps.calendars.google_calendar_service import GoogleCalendarService
    from apps.authentication.services.clerk_service import clerk_service
    
    try:
        if clerk_user_id:
            # Delete for specific user
            calendar_events = CalendarEvent.objects.select_related(
                'integration__user'
            ).filter(booking_id=booking_id, integration__user__clerk_user_id=clerk_user_id)
        else:
            # Delete for all users
            calendar_events = CalendarEvent.objects.select_related(
                'integration__user'
            ).filter(booking_id=booking_id)
        
        for calendar_event in calendar_events:
            if not calendar_event.google_event_id:
                calendar_event.delete()
                continue
            
            integration = calendar_event.integration
            
            # Fetch fresh Google OAuth token from Clerk
            token_data = clerk_service.get_google_oauth_token(integration.user.clerk_user_id)
            if not token_data or not token_data.get('token'):
                logger.warning(f"Could not get Google token for user {integration.user.email}")
                calendar_event.delete()
                continue
            
            calendar_service = GoogleCalendarService(token_data['token'])
            
            try:
                calendar_service.delete_booking_event(
                    calendar_event.google_event_id,
                    integration.google_calendar_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete Google event: {e}")
            
            calendar_event.delete()
            logger.info(f"Deleted calendar event for booking {booking_id} user {integration.user.email}")
    
    except Exception as e:
        logger.error(f"Failed to delete calendar event for booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_all_bookings_task(self, clerk_user_id: str):
    """
    Sync all future confirmed bookings for a user based on their role.
    - Customer: sync their booked appointments
    - Staff: sync their assigned appointments
    - Client: sync all bookings for their shops
    
    Args:
        clerk_user_id: Clerk user ID (primary key)
    """
    from django.utils import timezone
    from apps.authentication.models import User
    from apps.bookings.models import Booking
    from apps.customers.models import Customer
    from apps.staff.models import StaffMember
    from apps.clients.models import Client
    
    try:
        user = User.objects.get(clerk_user_id=clerk_user_id)
        
        booking_ids = set()
        
        # Get bookings based on user role
        if user.role == 'customer':
            # Customer: get their booked appointments
            try:
                customer = Customer.objects.get(user=user)
                customer_bookings = Booking.objects.filter(
                    customer=customer,
                    status='confirmed',
                    booking_datetime__gte=timezone.now()
                ).values_list('id', flat=True)
                booking_ids.update(customer_bookings)
            except Customer.DoesNotExist:
                pass
                
        elif user.role == 'staff':
            # Staff: get their assigned appointments
            try:
                staff = StaffMember.objects.get(user=user)
                staff_bookings = Booking.objects.filter(
                    staff_member=staff,
                    status='confirmed',
                    booking_datetime__gte=timezone.now()
                ).values_list('id', flat=True)
                booking_ids.update(staff_bookings)
            except StaffMember.DoesNotExist:
                pass
                
        elif user.role == 'client':
            # Client: get all bookings for their shops
            try:
                client = Client.objects.get(user=user)
                # Get all shops owned by this client
                from apps.shops.models import Shop
                shops = Shop.objects.filter(client=client)
                client_bookings = Booking.objects.filter(
                    shop__in=shops,
                    status='confirmed',
                    booking_datetime__gte=timezone.now()
                ).values_list('id', flat=True)
                booking_ids.update(client_bookings)
            except Client.DoesNotExist:
                pass
        
        if not booking_ids:
            logger.info(f"No bookings to sync for user {clerk_user_id}")
            return
        
        # Queue individual sync tasks
        for booking_id in booking_ids:
            sync_booking_for_user_task.delay(str(booking_id), clerk_user_id)
        
        logger.info(f"Queued {len(booking_ids)} bookings for sync for user {clerk_user_id} (role: {user.role})")
    
    except User.DoesNotExist:
        logger.warning(f"User {clerk_user_id} not found")
    except Exception as e:
        logger.error(f"Failed to sync all bookings for user {clerk_user_id}: {e}")
        raise self.retry(exc=e)


# Keep the old task name for backwards compatibility
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_booking_task(self, booking_id: str):
    """
    Legacy task - sync a booking to the customer's calendar only.
    Use sync_booking_for_user_task for new code.
    """
    from apps.bookings.models import Booking
    
    try:
        booking = Booking.objects.select_related('customer__user').get(id=booking_id)
        
        if booking.customer and booking.customer.user:
            sync_booking_for_user_task.delay(booking_id, booking.customer.user.clerk_user_id)
    
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found")
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id}: {e}")
        raise self.retry(exc=e)
