"""
Django signals for automatic notification triggering.
Handles booking events, staff changes, and shop holidays.
Comprehensive party-based notifications with FCM push and email.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Store original values for comparison in post_save
_booking_originals = {}


def send_push_notification(user, title: str, body: str, data: dict = None, notification_type: str = 'system'):
    """
    Helper to send FCM push notification to a user.
    Push notifications are always sent (not affected by email opt-out).
    """
    if not user:
        return
        
    try:
        from apps.notifications.services.fcm_service import FCMService
        logger.info(f"Sending push to {user.email}: {title}")
        
        sent_count = FCMService.send_to_user(
            user=user,
            title=title,
            body=body,
            data=data or {},
            notification_type=notification_type
        )
        
        if sent_count > 0:
            logger.info(f"Push sent ({sent_count}) to {user.email}")
        else:
            logger.debug(f"No active devices for {user.email}")
            
    except Exception as e:
        logger.error(f"Push failed for {user.email}: {e}")


def get_booking_parties(booking):
    """
    Get all parties involved in a booking.
    Returns dict with customer_user, staff_user, owner_user (any may be None).
    """
    parties = {
        'customer_user': None,
        'staff_user': None,
        'owner_user': None,
    }
    
    if booking.customer and booking.customer.user:
        parties['customer_user'] = booking.customer.user
    
    if booking.staff_member and booking.staff_member.user:
        parties['staff_user'] = booking.staff_member.user
    
    if booking.shop and hasattr(booking.shop, 'client') and booking.shop.client and booking.shop.client.user:
        parties['owner_user'] = booking.shop.client.user
    
    return parties


@receiver(pre_save, sender='bookings.Booking')
def booking_pre_save(sender, instance, **kwargs):
    """Capture original booking state before save."""
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
    Handle booking events with comprehensive party-based notifications.
    
    Notification Rules:
    - Booking Created: Customer + Staff + Owner all notified
    - Cancelled by Customer: Staff + Owner notified
    - Cancelled by Staff: Customer + Owner notified  
    - Cancelled by Owner: Customer + Staff notified
    - Rescheduled: All parties notified
    - Staff Changed: Customer + Old Staff + New Staff + Owner notified
    """
    from apps.notifications.tasks import (
        send_booking_confirmation_task,
        send_booking_cancellation_task,
        send_staff_assignment_task,
    )
    from apps.notifications.models import NotificationType
    
    booking_id = str(instance.id)
    
    # Handle both service and deal bookings
    if instance.service:
        item_name = instance.service.name
    elif instance.deal:
        item_name = f"Deal: {instance.deal.name}"
    else:
        item_name = 'Appointment'
    
    shop_name = instance.shop.name if instance.shop else 'Shop'
    parties = get_booking_parties(instance)
    
    # ===== NEW BOOKING =====
    if created:
        if instance.status in ['confirmed', 'pending']:
            # Queue email task (respects user preferences)
            try:
                send_booking_confirmation_task.delay(booking_id)
                logger.info(f"Queued confirmation emails for booking {booking_id}")
            except Exception as e:
                logger.error(f"Failed to queue confirmation: {e}")
            
            # Push to Customer
            send_push_notification(
                user=parties['customer_user'],
                title='Booking Confirmed! ✅',
                body=f'Your {item_name} at {shop_name} has been confirmed.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CONFIRMATION},
                notification_type=NotificationType.BOOKING_CONFIRMATION
            )
            
            # Push to Staff (only for service bookings)
            if instance.staff_member:
                send_push_notification(
                    user=parties['staff_user'],
                    title='New Booking Assigned 📅',
                    body=f'New {item_name} booking at {shop_name}.',
                    data={'booking_id': booking_id, 'type': NotificationType.NEW_BOOKING},
                    notification_type=NotificationType.NEW_BOOKING
                )
            
            # Push to Owner
            send_push_notification(
                user=parties['owner_user'],
                title='New Booking Received 🎉',
                body=f'New booking for {item_name}.',
                data={'booking_id': booking_id, 'type': NotificationType.NEW_BOOKING},
                notification_type=NotificationType.NEW_BOOKING
            )
        return
    
    # ===== EXISTING BOOKING CHANGES =====
    original = _booking_originals.pop(instance.pk, None)
    if not original:
        return
    
    # ----- CONFIRMATION (pending → confirmed) -----
    if instance.status == 'confirmed' and original['status'] == 'pending':
        # Queue confirmation email
        try:
            send_booking_confirmation_task.delay(booking_id)
            logger.info(f"Queued confirmation emails for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue confirmation: {e}")
        
        # Notify all parties
        send_push_notification(
            user=parties['customer_user'],
            title='Booking Confirmed! ✅',
            body=f'Your {item_name} booking at {shop_name} has been confirmed.',
            data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CONFIRMATION},
            notification_type=NotificationType.BOOKING_CONFIRMATION
        )
        if instance.staff_member:
            send_push_notification(
                user=parties['staff_user'],
                title='Booking Confirmed',
                body=f'A {item_name} booking has been confirmed.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CONFIRMATION},
                notification_type=NotificationType.BOOKING_CONFIRMATION
            )
        send_push_notification(
            user=parties['owner_user'],
            title='Booking Confirmed',
            body=f'A {item_name} booking has been confirmed.',
            data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CONFIRMATION},
            notification_type=NotificationType.BOOKING_CONFIRMATION
        )
        return
    
    # ----- CANCELLATION -----
    if instance.status == 'cancelled' and original['status'] != 'cancelled':
        cancelled_by = instance.cancelled_by or 'customer'
        
        # Queue email task
        try:
            send_booking_cancellation_task.delay(booking_id, cancelled_by)
            logger.info(f"Queued cancellation emails for booking {booking_id} (by {cancelled_by})")
        except Exception as e:
            logger.error(f"Failed to queue cancellation: {e}")
        
        # Notify parties based on who cancelled
        if cancelled_by == 'customer':
            # Staff + Owner get notified
            if instance.staff_member:
                send_push_notification(
                    user=parties['staff_user'],
                    title='Booking Cancelled ❌',
                    body=f'Customer cancelled their {item_name} booking.',
                    data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                    notification_type=NotificationType.BOOKING_CANCELLATION
                )
            send_push_notification(
                user=parties['owner_user'],
                title='Booking Cancelled',
                body=f'A {item_name} booking was cancelled by customer.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
            
        elif cancelled_by == 'staff':
            # Customer + Owner get notified
            send_push_notification(
                user=parties['customer_user'],
                title='Booking Cancelled ❌',
                body=f'Your {item_name} booking has been cancelled.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
            send_push_notification(
                user=parties['owner_user'],
                title='Booking Cancelled by Staff',
                body=f'A {item_name} booking was cancelled by staff.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
            
        elif cancelled_by in ['owner', 'system']:
            # Customer + Staff get notified
            send_push_notification(
                user=parties['customer_user'],
                title='Booking Cancelled ❌',
                body=f'Your {item_name} booking has been cancelled by the shop.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
            if instance.staff_member:
                send_push_notification(
                    user=parties['staff_user'],
                    title='Booking Cancelled',
                    body=f'A {item_name} booking was cancelled by owner.',
                    data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                    notification_type=NotificationType.BOOKING_CANCELLATION
                )
        return
    
    # ----- STAFF MEMBER CHANGE -----
    if original['staff_member_id'] != instance.staff_member_id:
        old_staff_id = str(original['staff_member_id']) if original['staff_member_id'] else None
        new_staff_id = str(instance.staff_member_id) if instance.staff_member_id else None
        
        # Queue email task
        try:
            send_staff_assignment_task.delay(booking_id, old_staff_id, new_staff_id)
            logger.info(f"Queued staff assignment emails for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue staff assignment: {e}")
        
        # Notify customer
        send_push_notification(
            user=parties['customer_user'],
            title='Staff Member Changed',
            body=f'Your {item_name} booking has a new staff member.',
            data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
            notification_type=NotificationType.STAFF_ASSIGNMENT
        )
        
        # Notify new staff
        send_push_notification(
            user=parties['staff_user'],
            title='Booking Assigned to You 📅',
            body=f'You have been assigned to a {item_name} booking.',
            data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
            notification_type=NotificationType.STAFF_ASSIGNMENT
        )
        
        # Notify old staff (need to fetch their user)
        if old_staff_id:
            try:
                from apps.staff.models import StaffMember
                old_staff = StaffMember.objects.select_related('user').get(id=old_staff_id)
                if old_staff.user:
                    send_push_notification(
                        user=old_staff.user,
                        title='Booking Unassigned',
                        body=f'You have been unassigned from a {item_name} booking.',
                        data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
                        notification_type=NotificationType.STAFF_ASSIGNMENT
                    )
            except Exception as e:
                logger.warning(f"Could not notify old staff: {e}")
        
        # Notify owner
        send_push_notification(
            user=parties['owner_user'],
            title='Staff Assignment Changed',
            body=f'Staff member changed for a {item_name} booking.',
            data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
            notification_type=NotificationType.STAFF_ASSIGNMENT
        )
    
    # ----- RESCHEDULE (DATETIME CHANGE) -----
    if original['booking_datetime'] != instance.booking_datetime:
        # Queue email task for reschedule
        try:
            send_booking_confirmation_task.delay(booking_id)
            logger.info(f"Queued reschedule emails for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue reschedule: {e}")
        
        # Notify all parties about reschedule
        send_push_notification(
            user=parties['customer_user'],
            title='Booking Rescheduled 📅',
            body=f'Your {item_name} booking has been rescheduled.',
            data={'booking_id': booking_id, 'type': NotificationType.BOOKING_RESCHEDULE},
            notification_type=NotificationType.BOOKING_RESCHEDULE
        )
        if instance.staff_member:
            send_push_notification(
                user=parties['staff_user'],
                title='Booking Rescheduled',
                body=f'A {item_name} booking has been rescheduled.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_RESCHEDULE},
                notification_type=NotificationType.BOOKING_RESCHEDULE
            )
        send_push_notification(
            user=parties['owner_user'],
            title='Booking Rescheduled',
            body=f'A {item_name} booking has been rescheduled.',
            data={'booking_id': booking_id, 'type': NotificationType.BOOKING_RESCHEDULE},
            notification_type=NotificationType.BOOKING_RESCHEDULE
        )


@receiver(post_save, sender='schedules.Holiday')
def shop_holiday_created(sender, instance, created, **kwargs):
    """
    Handle shop holiday creation and notify affected customers.
    """
    if not created:
        return
    
    from apps.notifications.tasks import send_shop_holiday_notification_task
    from apps.notifications.models import NotificationType
    
    try:
        shop_id = str(instance.shop_id)
        holiday_date = instance.date.isoformat()
        send_shop_holiday_notification_task.delay(shop_id, holiday_date)
        logger.info(f"Queued holiday notifications for shop {shop_id} on {holiday_date}")
        
        # Also send push to shop owner about holiday creation
        if instance.shop and hasattr(instance.shop, 'client') and instance.shop.client and instance.shop.client.user:
            send_push_notification(
                user=instance.shop.client.user,
                title='Holiday Created',
                body=f'Shop holiday set for {instance.date.strftime("%b %d, %Y")}. Affected customers will be notified.',
                data={'holiday_date': holiday_date, 'type': NotificationType.SHOP_HOLIDAY},
                notification_type=NotificationType.SHOP_HOLIDAY
            )
    except Exception as e:
        logger.error(f"Failed to queue holiday notifications: {e}")


@receiver(post_save, sender='authentication.User')
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create default notification preferences for new users."""
    if created:
        from apps.notifications.models import NotificationPreference
        
        try:
            NotificationPreference.objects.create(user=instance)
            logger.debug(f"Created notification preferences for {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create preferences for {instance.email}: {e}")
