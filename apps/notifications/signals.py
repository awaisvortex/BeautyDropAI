"""
Django signals for automatic notification triggering.
Handles booking events, staff changes, and shop holidays.
Now with Firebase Cloud Messaging push notifications.
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
    Fails silently to not block the main flow.
    """
    try:
        from apps.notifications.services.fcm_service import FCMService
        FCMService.send_to_user(
            user=user,
            title=title,
            body=body,
            data=data or {},
            notification_type=notification_type
        )
    except Exception as e:
        logger.warning(f"Failed to send push notification to {user.email}: {e}")


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
    
    Triggers emails and push notifications for:
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
    from apps.notifications.models import NotificationType
    
    booking_id = str(instance.id)
    service_name = instance.service.name if instance.service else 'Service'
    shop_name = instance.shop.name if instance.shop else 'Shop'
    
    if created:
        # New booking - send confirmation if confirmed or pending
        if instance.status in ['confirmed', 'pending']:
            try:
                send_booking_confirmation_task.delay(booking_id)
                logger.info(f"Queued confirmation email for new booking {booking_id}")
            except Exception as e:
                logger.error(f"Failed to queue confirmation for booking {booking_id}: {e}")
            
            # Send push to customer
            if instance.customer and instance.customer.user:
                send_push_notification(
                    user=instance.customer.user,
                    title='Booking Confirmed! ✅',
                    body=f'Your {service_name} at {shop_name} has been confirmed.',
                    data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CONFIRMATION},
                    notification_type=NotificationType.BOOKING_CONFIRMATION
                )
            
            # Send push to staff member (new booking assigned)
            if instance.staff_member and instance.staff_member.user:
                send_push_notification(
                    user=instance.staff_member.user,
                    title='New Booking Assigned 📅',
                    body=f'You have a new {service_name} booking.',
                    data={'booking_id': booking_id, 'type': NotificationType.NEW_BOOKING},
                    notification_type=NotificationType.NEW_BOOKING
                )
            
            # Send push to shop owner
            if instance.shop and hasattr(instance.shop, 'client') and instance.shop.client and instance.shop.client.user:
                send_push_notification(
                    user=instance.shop.client.user,
                    title='New Booking Received 🎉',
                    body=f'New booking for {service_name}.',
                    data={'booking_id': booking_id, 'type': NotificationType.NEW_BOOKING},
                    notification_type=NotificationType.NEW_BOOKING
                )
        return
    
    # Existing booking - check for changes
    original = _booking_originals.pop(instance.pk, None)
    if not original:
        return
    
    # Check for cancellation
    if instance.status == 'cancelled' and original['status'] != 'cancelled':
        try:
            cancelled_by = 'customer'  # Default assumption
            send_booking_cancellation_task.delay(booking_id, cancelled_by)
            logger.info(f"Queued cancellation email for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue cancellation for booking {booking_id}: {e}")
        
        # Send push to customer
        if instance.customer and instance.customer.user:
            send_push_notification(
                user=instance.customer.user,
                title='Booking Cancelled ❌',
                body=f'Your {service_name} booking has been cancelled.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
        
        # Send push to staff member
        if instance.staff_member and instance.staff_member.user:
            send_push_notification(
                user=instance.staff_member.user,
                title='Booking Cancelled',
                body=f'A {service_name} booking has been cancelled.',
                data={'booking_id': booking_id, 'type': NotificationType.BOOKING_CANCELLATION},
                notification_type=NotificationType.BOOKING_CANCELLATION
            )
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
        
        # Send push to customer about staff change
        if instance.customer and instance.customer.user:
            send_push_notification(
                user=instance.customer.user,
                title='Staff Member Changed',
                body=f'Your {service_name} booking has a new staff member assigned.',
                data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
                notification_type=NotificationType.STAFF_ASSIGNMENT
            )
        
        # Send push to new staff member
        if instance.staff_member and instance.staff_member.user:
            send_push_notification(
                user=instance.staff_member.user,
                title='New Booking Assigned 📅',
                body=f'You have been assigned to a {service_name} booking.',
                data={'booking_id': booking_id, 'type': NotificationType.STAFF_ASSIGNMENT},
                notification_type=NotificationType.STAFF_ASSIGNMENT
            )
    
    # Check for reschedule (datetime change)
    if original['booking_datetime'] != instance.booking_datetime:
        try:
            send_booking_confirmation_task.delay(booking_id)
            logger.info(f"Queued reschedule notification for booking {booking_id}")
        except Exception as e:
            logger.error(f"Failed to queue reschedule for booking {booking_id}: {e}")
        
        # Send push to customer about reschedule
        if instance.customer and instance.customer.user:
            send_push_notification(
                user=instance.customer.user,
                title='Booking Rescheduled 📅',
                body=f'Your {service_name} booking has been rescheduled.',
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
