"""
Celery tasks for email notifications.
Handles async email sending and scheduled booking reminders.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email_task(
    self,
    notification_type: str,
    recipient_email: str,
    recipient_name: str,
    context: dict,
    booking_id: str = None,
    user_id: str = None
):
    """
    Async task to send a single notification email.
    
    Args:
        notification_type: Type of notification (from NotificationType)
        recipient_email: Recipient's email address
        recipient_name: Recipient's name
        context: Template context dictionary
        booking_id: Optional booking UUID for deduplication
        user_id: Optional user ID for preference checking
    """
    from apps.notifications.services.email_service import EmailNotificationService
    from apps.bookings.models import Booking
    from apps.authentication.models import User
    
    try:
        booking = None
        user = None
        
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                logger.warning(f"Booking {booking_id} not found for notification")
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found for notification preferences")
        
        EmailNotificationService.send_email(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            notification_type=notification_type,
            context=context,
            booking=booking,
            user=user
        )
        
        logger.info(f"Email task completed: {notification_type} to {recipient_email}")
        
    except Exception as e:
        logger.error(f"Email task failed: {notification_type} to {recipient_email}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_booking_reminders_task(self):
    """
    Periodic task to send booking reminder emails.
    Runs hourly via Celery Beat.
    
    Checks for:
    - Bookings in ~24 hours: Send 1-day reminder
    - Bookings in ~1 hour: Send 1-hour reminder
    """
    from apps.bookings.models import Booking
    from apps.notifications.services.email_service import EmailNotificationService
    from apps.notifications.models import NotificationType
    
    now = timezone.now()
    
    # 1-Day Reminder Window: 23.5 to 24.5 hours from now
    # This gives a 1-hour window to catch bookings
    day_reminder_start = now + timedelta(hours=23, minutes=30)
    day_reminder_end = now + timedelta(hours=24, minutes=30)
    
    # 1-Hour Reminder Window: 45 minutes to 1.25 hours from now
    hour_reminder_start = now + timedelta(minutes=45)
    hour_reminder_end = now + timedelta(hours=1, minutes=15)
    
    logger.info(f"Running booking reminders check at {now}")
    
    sent_count = 0
    skipped_count = 0
    
    try:
        # Find bookings needing 1-day reminder
        day_bookings = Booking.objects.filter(
            booking_datetime__gte=day_reminder_start,
            booking_datetime__lt=day_reminder_end,
            status__in=['confirmed', 'pending']
        ).select_related(
            'customer__user',
            'staff_member__user',
            'shop',
            'service'
        )
        
        for booking in day_bookings:
            try:
                logs = EmailNotificationService.send_booking_reminder(
                    booking=booking,
                    reminder_type=NotificationType.BOOKING_REMINDER_1DAY
                )
                sent_count += len(logs)
                if not logs:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to send 1-day reminder for booking {booking.id}: {e}")
        
        # Find bookings needing 1-hour reminder
        hour_bookings = Booking.objects.filter(
            booking_datetime__gte=hour_reminder_start,
            booking_datetime__lt=hour_reminder_end,
            status__in=['confirmed', 'pending']
        ).select_related(
            'customer__user',
            'staff_member__user',
            'shop',
            'service'
        )
        
        for booking in hour_bookings:
            try:
                logs = EmailNotificationService.send_booking_reminder(
                    booking=booking,
                    reminder_type=NotificationType.BOOKING_REMINDER_1HOUR
                )
                sent_count += len(logs)
                if not logs:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to send 1-hour reminder for booking {booking.id}: {e}")
        
        logger.info(
            f"Booking reminders completed: {sent_count} sent, {skipped_count} skipped "
            f"(duplicates/opted-out)"
        )
        
    except Exception as e:
        logger.error(f"Booking reminders task failed: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation_task(self, booking_id: str):
    """
    Send booking confirmation emails to all parties.
    
    Args:
        booking_id: UUID of the confirmed booking
    """
    from apps.bookings.models import Booking
    from apps.notifications.services.email_service import EmailNotificationService
    
    try:
        booking = Booking.objects.select_related(
            'customer__user',
            'staff_member__user',
            'shop__client__user',
            'service'
        ).get(id=booking_id)
        
        logs = EmailNotificationService.send_booking_confirmation(booking)
        logger.info(f"Sent {len(logs)} confirmation emails for booking {booking_id}")
        
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found for confirmation email")
    except Exception as e:
        logger.error(f"Failed to send confirmation for booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_cancellation_task(self, booking_id: str, cancelled_by: str = 'customer'):
    """
    Send booking cancellation emails to all parties.
    
    Args:
        booking_id: UUID of the cancelled booking
        cancelled_by: Who cancelled ('customer', 'shop', 'system')
    """
    from apps.bookings.models import Booking
    from apps.notifications.services.email_service import EmailNotificationService
    
    try:
        booking = Booking.objects.select_related(
            'customer__user',
            'staff_member__user',
            'shop__client__user',
            'service'
        ).get(id=booking_id)
        
        logs = EmailNotificationService.send_booking_cancellation(booking, cancelled_by)
        logger.info(f"Sent {len(logs)} cancellation emails for booking {booking_id}")
        
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found for cancellation email")
    except Exception as e:
        logger.error(f"Failed to send cancellation for booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_staff_assignment_task(
    self,
    booking_id: str,
    old_staff_id: str = None,
    new_staff_id: str = None
):
    """
    Send staff assignment change notifications.
    
    Args:
        booking_id: UUID of the booking
        old_staff_id: UUID of the previous staff member
        new_staff_id: UUID of the new staff member
    """
    from apps.bookings.models import Booking
    from apps.staff.models import StaffMember
    from apps.notifications.services.email_service import EmailNotificationService
    
    try:
        booking = Booking.objects.select_related(
            'customer__user',
            'shop__client__user',
            'service'
        ).get(id=booking_id)
        
        old_staff = None
        new_staff = None
        
        if old_staff_id:
            try:
                old_staff = StaffMember.objects.select_related('user').get(id=old_staff_id)
            except StaffMember.DoesNotExist:
                pass
        
        if new_staff_id:
            try:
                new_staff = StaffMember.objects.select_related('user').get(id=new_staff_id)
            except StaffMember.DoesNotExist:
                pass
        
        logs = EmailNotificationService.send_staff_assignment_notification(
            booking=booking,
            old_staff=old_staff,
            new_staff=new_staff
        )
        logger.info(f"Sent {len(logs)} staff assignment emails for booking {booking_id}")
        
    except Booking.DoesNotExist:
        logger.warning(f"Booking {booking_id} not found for staff assignment email")
    except Exception as e:
        logger.error(f"Failed to send staff assignment for booking {booking_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_shop_holiday_notification_task(self, shop_id: str, holiday_date: str):
    """
    Send shop holiday notifications to affected customers.
    
    Args:
        shop_id: UUID of the shop
        holiday_date: Date string in ISO format
    """
    from datetime import datetime
    from apps.shops.models import Shop
    from apps.bookings.models import Booking
    from apps.notifications.services.email_service import EmailNotificationService
    
    try:
        shop = Shop.objects.get(id=shop_id)
        holiday = datetime.fromisoformat(holiday_date).date()
        
        # Find all bookings on this holiday
        affected_bookings = Booking.objects.filter(
            shop=shop,
            booking_datetime__date=holiday,
            status__in=['confirmed', 'pending']
        ).select_related(
            'customer__user',
            'service'
        )
        
        if affected_bookings.exists():
            logs = EmailNotificationService.send_shop_holiday_notification(
                shop=shop,
                holiday_date=holiday,
                affected_bookings=list(affected_bookings)
            )
            logger.info(
                f"Sent {len(logs)} holiday notifications for shop {shop.name} on {holiday}"
            )
        else:
            logger.info(f"No affected bookings for shop {shop.name} holiday on {holiday}")
        
    except Shop.DoesNotExist:
        logger.warning(f"Shop {shop_id} not found for holiday notification")
    except Exception as e:
        logger.error(f"Failed to send holiday notifications for shop {shop_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def retry_failed_emails_task(self):
    """
    Retry sending failed email notifications.
    Runs periodically to handle transient failures.
    """
    from apps.notifications.models import EmailNotificationLog, NotificationStatus
    from apps.notifications.services.email_service import EmailNotificationService
    
    # Find failed emails that haven't exceeded retry limit
    failed_emails = EmailNotificationLog.objects.filter(
        status=NotificationStatus.FAILED,
        retry_count__lt=3,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('booking', 'notification')[:50]  # Process 50 at a time
    
    retried = 0
    for email_log in failed_emails:
        try:
            # Queue for retry via the main email task
            send_notification_email_task.delay(
                notification_type=email_log.email_type,
                recipient_email=email_log.recipient_email,
                recipient_name=email_log.recipient_name,
                context={},  # Context would need to be rebuilt from booking
                booking_id=str(email_log.booking.id) if email_log.booking else None
            )
            retried += 1
        except Exception as e:
            logger.error(f"Failed to queue retry for email {email_log.id}: {e}")
    
    logger.info(f"Queued {retried} failed emails for retry")
