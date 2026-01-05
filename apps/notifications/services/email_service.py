"""
Email notification service for BeautyDropAI.
Handles all email sending operations via Mailgun using django-anymail.
"""
import logging
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.db import IntegrityError

from apps.notifications.models import (
    Notification,
    EmailNotificationLog,
    NotificationPreference,
    NotificationType,
    NotificationStatus
)

logger = logging.getLogger(__name__)


# --- Null-Safe Helper Functions ---

def get_customer_email(booking) -> Optional[str]:
    """Get customer email safely, handling null customer or user."""
    if booking.customer and booking.customer.user:
        return booking.customer.user.email
    return None


def get_customer_name(booking) -> str:
    """Get customer name safely, handling null customer or user."""
    if booking.customer:
        if booking.customer.user:
            return booking.customer.user.full_name or booking.customer.user.email
        # Fallback to customer email if user not linked
        if hasattr(booking.customer, 'email') and booking.customer.email:
            return booking.customer.email
    return 'Customer'


def get_customer_user(booking):
    """Get customer's user safely, may return None."""
    if booking.customer:
        return booking.customer.user
    return None


def get_staff_email(staff_member) -> Optional[str]:
    """Get staff email safely, preferring user email over staff email."""
    if staff_member:
        if staff_member.user and staff_member.user.email:
            return staff_member.user.email
        return staff_member.email
    return None


def get_staff_name(staff_member) -> str:
    """Get staff name safely, handling null user."""
    if staff_member:
        if staff_member.user:
            return staff_member.user.full_name or staff_member.name
        return staff_member.name
    return 'Staff Member'


def get_staff_user(staff_member):
    """Get staff's user safely, may return None."""
    if staff_member:
        return staff_member.user
    return None


def get_client_email(shop) -> Optional[str]:
    """Get shop owner email safely."""
    if shop and hasattr(shop, 'client') and shop.client and shop.client.user:
        return shop.client.user.email
    return None


def get_client_name(shop) -> str:
    """Get shop owner name safely."""
    if shop and hasattr(shop, 'client') and shop.client and shop.client.user:
        return shop.client.user.full_name or shop.client.user.email
    return 'Shop Owner'


def get_client_user(shop):
    """Get shop owner's user safely, may return None."""
    if shop and hasattr(shop, 'client') and shop.client:
        return shop.client.user
    return None


class EmailNotificationService:
    """
    Service class for sending email notifications.
    Handles all notification types with proper error handling and logging.
    """
    
    TEMPLATE_MAP = {
        NotificationType.BOOKING_CONFIRMATION: 'emails/booking_confirmation.html',
        NotificationType.BOOKING_CANCELLATION: 'emails/booking_cancellation.html',
        NotificationType.BOOKING_RESCHEDULE: 'emails/booking_reschedule.html',
        NotificationType.BOOKING_REMINDER_1DAY: 'emails/booking_reminder.html',
        NotificationType.BOOKING_REMINDER_1HOUR: 'emails/booking_reminder.html',
        NotificationType.STAFF_ASSIGNMENT: 'emails/staff_assignment.html',
        NotificationType.SHOP_HOLIDAY: 'emails/shop_holiday.html',
    }
    
    SUBJECT_MAP = {
        NotificationType.BOOKING_CONFIRMATION: 'Your Booking is Confirmed - {shop_name}',
        NotificationType.BOOKING_CANCELLATION: 'Booking Cancelled - {shop_name}',
        NotificationType.BOOKING_RESCHEDULE: 'Your Booking has been Rescheduled - {shop_name}',
        NotificationType.BOOKING_REMINDER_1DAY: 'Reminder: Your Appointment Tomorrow at {shop_name}',
        NotificationType.BOOKING_REMINDER_1HOUR: 'Reminder: Your Appointment in 1 Hour at {shop_name}',
        NotificationType.STAFF_ASSIGNMENT: 'Staff Member Changed for Your Booking - {shop_name}',
        NotificationType.SHOP_HOLIDAY: 'Shop Holiday Notice - {shop_name}',
    }
    
    @classmethod
    def get_user_preferences(cls, user) -> NotificationPreference:
        """
        Get or create notification preferences for a user.
        
        Args:
            user: User instance
            
        Returns:
            NotificationPreference instance
        """
        preferences, _ = NotificationPreference.objects.get_or_create(user=user)
        return preferences
    
    @classmethod
    def is_notification_enabled(cls, user, notification_type: str) -> bool:
        """
        Check if a notification type is enabled for a user.
        
        Args:
            user: User instance
            notification_type: NotificationType value
            
        Returns:
            bool: True if notification is enabled
        """
        if not user or not user.email:
            return False
        
        preferences = cls.get_user_preferences(user)
        return preferences.is_email_enabled(notification_type)
    
    @classmethod
    def check_duplicate_reminder(cls, booking, email_type: str, recipient_email: str) -> bool:
        """
        Check if a reminder has already been sent for this booking.
        
        Args:
            booking: Booking instance
            email_type: The notification type
            recipient_email: Recipient's email
            
        Returns:
            bool: True if duplicate exists
        """
        return EmailNotificationLog.objects.filter(
            booking=booking,
            email_type=email_type,
            recipient_email=recipient_email,
            status__in=[NotificationStatus.SENT, NotificationStatus.DELIVERED]
        ).exists()
    
    @classmethod
    def send_email(
        cls,
        recipient_email: str,
        recipient_name: str,
        notification_type: str,
        context: Dict[str, Any],
        booking=None,
        user=None,
        notification: Optional[Notification] = None
    ) -> Optional[EmailNotificationLog]:
        """
        Send an email notification.
        
        Args:
            recipient_email: Recipient's email address
            recipient_name: Recipient's name
            notification_type: Type of notification (from NotificationType)
            context: Template context dictionary
            booking: Optional booking instance for deduplication
            user: Optional user for preference checking
            notification: Optional related Notification instance
            
        Returns:
            EmailNotificationLog instance or None if failed/skipped
        """
        # Validate email
        if not recipient_email:
            logger.warning(f"Skipping notification {notification_type}: no recipient email")
            return None
        
        # Check user preferences
        if user and not cls.is_notification_enabled(user, notification_type):
            logger.info(f"User {user.email} has disabled {notification_type} notifications")
            return None
        
        # Check for duplicate reminders
        if booking and notification_type in [
            NotificationType.BOOKING_REMINDER_1DAY,
            NotificationType.BOOKING_REMINDER_1HOUR
        ]:
            if cls.check_duplicate_reminder(booking, notification_type, recipient_email):
                logger.info(f"Skipping duplicate {notification_type} for booking {booking.id}")
                return None
        
        # Get template and subject
        template_name = cls.TEMPLATE_MAP.get(notification_type)
        subject_template = cls.SUBJECT_MAP.get(notification_type, 'BeautyDrop Notification')
        
        if not template_name:
            logger.error(f"No template found for notification type: {notification_type}")
            return None
        
        # Build subject
        subject = subject_template.format(
            shop_name=context.get('shop_name', 'BeautyDrop'),
            service_name=context.get('service_name', ''),
        )
        
        # Create log entry first (for deduplication)
        try:
            email_log = EmailNotificationLog.objects.create(
                notification=notification,
                email_type=notification_type,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                status=NotificationStatus.PENDING,
                booking=booking
            )
        except IntegrityError:
            # Duplicate constraint violation - already sent
            logger.info(f"Duplicate notification prevented: {notification_type} for {recipient_email}")
            return None
        
        try:
            # Render template
            context['recipient_name'] = recipient_name
            context['current_year'] = timezone.now().year
            html_content = render_to_string(template_name, context)
            text_content = strip_tags(html_content)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            # Update log with success
            email_log.status = NotificationStatus.SENT
            email_log.sent_at = timezone.now()
            email_log.save()
            
            logger.info(f"Email sent successfully: {notification_type} to {recipient_email}")
            return email_log
            
        except Exception as e:
            # Update log with failure
            email_log.status = NotificationStatus.FAILED
            email_log.error_message = str(e)
            email_log.retry_count += 1
            email_log.save()
            
            logger.error(f"Failed to send email {notification_type} to {recipient_email}: {e}")
            raise
    
    @classmethod
    def send_booking_confirmation(cls, booking) -> List[EmailNotificationLog]:
        """
        Send booking confirmation emails to customer, staff, and shop owner.
        
        Args:
            booking: Booking instance
            
        Returns:
            List of EmailNotificationLog instances
        """
        logs = []
        context = cls._build_booking_context(booking)
        
        # Send to customer
        customer_email = get_customer_email(booking)
        if customer_email:
            customer_log = cls.send_email(
                recipient_email=customer_email,
                recipient_name=get_customer_name(booking),
                notification_type=NotificationType.BOOKING_CONFIRMATION,
                context={**context, 'is_customer': True},
                booking=booking,
                user=get_customer_user(booking)
            )
            if customer_log:
                logs.append(customer_log)
        
        # Send to staff member
        staff_email = get_staff_email(booking.staff_member)
        if staff_email:
            staff_log = cls.send_email(
                recipient_email=staff_email,
                recipient_name=get_staff_name(booking.staff_member),
                notification_type=NotificationType.BOOKING_CONFIRMATION,
                context={**context, 'is_staff': True},
                booking=booking,
                user=get_staff_user(booking.staff_member)
            )
            if staff_log:
                logs.append(staff_log)
        
        # Send to shop owner
        client_email = get_client_email(booking.shop)
        if client_email:
            owner_log = cls.send_email(
                recipient_email=client_email,
                recipient_name=get_client_name(booking.shop),
                notification_type=NotificationType.BOOKING_CONFIRMATION,
                context={**context, 'is_owner': True},
                booking=booking,
                user=get_client_user(booking.shop)
            )
            if owner_log:
                logs.append(owner_log)
        
        return logs
    
    @classmethod
    def send_booking_cancellation(cls, booking, cancelled_by: str = 'customer') -> List[EmailNotificationLog]:
        """
        Send booking cancellation emails.
        
        Args:
            booking: Booking instance
            cancelled_by: Who cancelled ('customer', 'shop', 'system')
            
        Returns:
            List of EmailNotificationLog instances
        """
        logs = []
        context = cls._build_booking_context(booking)
        context['cancelled_by'] = cancelled_by
        context['cancellation_reason'] = booking.cancellation_reason
        
        # Send to customer (if shop cancelled)
        if cancelled_by != 'customer':
            customer_email = get_customer_email(booking)
            if customer_email:
                customer_log = cls.send_email(
                    recipient_email=customer_email,
                    recipient_name=get_customer_name(booking),
                    notification_type=NotificationType.BOOKING_CANCELLATION,
                    context={**context, 'is_customer': True},
                    booking=booking,
                    user=get_customer_user(booking)
                )
                if customer_log:
                    logs.append(customer_log)
        
        # Send to staff member
        staff_email = get_staff_email(booking.staff_member)
        if staff_email:
            staff_log = cls.send_email(
                recipient_email=staff_email,
                recipient_name=get_staff_name(booking.staff_member),
                notification_type=NotificationType.BOOKING_CANCELLATION,
                context={**context, 'is_staff': True},
                booking=booking,
                user=get_staff_user(booking.staff_member)
            )
            if staff_log:
                logs.append(staff_log)
        
        # Send to shop owner (if customer cancelled)
        if cancelled_by == 'customer':
            client_email = get_client_email(booking.shop)
            if client_email:
                owner_log = cls.send_email(
                    recipient_email=client_email,
                    recipient_name=get_client_name(booking.shop),
                    notification_type=NotificationType.BOOKING_CANCELLATION,
                    context={**context, 'is_owner': True},
                    booking=booking,
                    user=get_client_user(booking.shop)
                )
                if owner_log:
                    logs.append(owner_log)
        
        return logs
    
    @classmethod
    def send_booking_reminder(
        cls,
        booking,
        reminder_type: str = NotificationType.BOOKING_REMINDER_1DAY
    ) -> List[EmailNotificationLog]:
        """
        Send booking reminder emails.
        
        Args:
            booking: Booking instance
            reminder_type: Type of reminder (1-day or 1-hour)
            
        Returns:
            List of EmailNotificationLog instances
        """
        # Skip if booking is cancelled or completed
        if booking.status not in ['confirmed', 'pending']:
            logger.info(f"Skipping reminder for booking {booking.id} with status {booking.status}")
            return []
        
        logs = []
        context = cls._build_booking_context(booking)
        context['is_1hour'] = reminder_type == NotificationType.BOOKING_REMINDER_1HOUR
        context['is_1day'] = reminder_type == NotificationType.BOOKING_REMINDER_1DAY
        
        # Send to customer
        customer_email = get_customer_email(booking)
        if customer_email:
            customer_log = cls.send_email(
                recipient_email=customer_email,
                recipient_name=get_customer_name(booking),
                notification_type=reminder_type,
                context={**context, 'is_customer': True},
                booking=booking,
                user=get_customer_user(booking)
            )
            if customer_log:
                logs.append(customer_log)
        
        # Send to staff member
        staff_email = get_staff_email(booking.staff_member)
        if staff_email:
            staff_log = cls.send_email(
                recipient_email=staff_email,
                recipient_name=get_staff_name(booking.staff_member),
                notification_type=reminder_type,
                context={**context, 'is_staff': True},
                booking=booking,
                user=get_staff_user(booking.staff_member)
            )
            if staff_log:
                logs.append(staff_log)
        
        return logs
    
    @classmethod
    def send_staff_assignment_notification(
        cls,
        booking,
        old_staff=None,
        new_staff=None
    ) -> List[EmailNotificationLog]:
        """
        Send notification when staff member is changed for a booking.
        
        Args:
            booking: Booking instance
            old_staff: Previous StaffMember (if any)
            new_staff: New StaffMember
            
        Returns:
            List of EmailNotificationLog instances
        """
        logs = []
        context = cls._build_booking_context(booking)
        context['old_staff_name'] = get_staff_name(old_staff) if old_staff else 'Not assigned'
        context['new_staff_name'] = get_staff_name(new_staff) if new_staff else 'Not assigned'
        
        # Send to customer
        customer_email = get_customer_email(booking)
        if customer_email:
            customer_log = cls.send_email(
                recipient_email=customer_email,
                recipient_name=get_customer_name(booking),
                notification_type=NotificationType.STAFF_ASSIGNMENT,
                context={**context, 'is_customer': True},
                booking=booking,
                user=get_customer_user(booking)
            )
            if customer_log:
                logs.append(customer_log)
        
        # Send to new staff
        new_staff_email = get_staff_email(new_staff)
        if new_staff_email:
            new_staff_log = cls.send_email(
                recipient_email=new_staff_email,
                recipient_name=get_staff_name(new_staff),
                notification_type=NotificationType.STAFF_ASSIGNMENT,
                context={**context, 'is_new_staff': True},
                booking=booking,
                user=get_staff_user(new_staff)
            )
            if new_staff_log:
                logs.append(new_staff_log)
        
        # Send to old staff (letting them know they're no longer assigned)
        old_staff_email = get_staff_email(old_staff)
        if old_staff_email:
            old_staff_log = cls.send_email(
                recipient_email=old_staff_email,
                recipient_name=get_staff_name(old_staff),
                notification_type=NotificationType.STAFF_ASSIGNMENT,
                context={**context, 'is_old_staff': True},
                booking=booking,
                user=get_staff_user(old_staff)
            )
            if old_staff_log:
                logs.append(old_staff_log)
        
        return logs
    
    @classmethod
    def send_shop_holiday_notification(
        cls,
        shop,
        holiday_date,
        affected_bookings: List
    ) -> List[EmailNotificationLog]:
        """
        Send notification about shop holiday to affected customers.
        
        Args:
            shop: Shop instance
            holiday_date: Date of the holiday
            affected_bookings: List of affected booking instances
            
        Returns:
            List of EmailNotificationLog instances
        """
        logs = []
        context = {
            'shop_name': shop.name,
            'shop_address': shop.address,
            'holiday_date': holiday_date,
        }
        
        # Track notified emails to avoid duplicates
        notified_emails = set()
        
        for booking in affected_bookings:
            customer_email = get_customer_email(booking)
            if customer_email and customer_email not in notified_emails:
                # Handle both service and deal bookings
                if booking.service:
                    item_name = booking.service.name
                elif booking.deal:
                    item_name = booking.deal.name
                else:
                    item_name = "Appointment"
                
                customer_log = cls.send_email(
                    recipient_email=customer_email,
                    recipient_name=get_customer_name(booking),
                    notification_type=NotificationType.SHOP_HOLIDAY,
                    context={
                        **context,
                        'booking_datetime': booking.booking_datetime,
                        'item_name': item_name,
                        'is_deal_booking': booking.is_deal_booking,
                    },
                    booking=booking,
                    user=get_customer_user(booking)
                )
                if customer_log:
                    logs.append(customer_log)
                    notified_emails.add(customer_email)
        
        return logs
    
    @classmethod
    def _build_booking_context(cls, booking) -> Dict[str, Any]:
        """
        Build common context dictionary for booking-related emails.
        
        Args:
            booking: Booking instance
            
        Returns:
            Dictionary with booking context
        """
        # Handle both service and deal bookings
        if booking.service:
            item_name = booking.service.name
            duration = booking.service.duration_minutes
        elif booking.deal:
            item_name = booking.deal.name
            duration = booking.duration_minutes
        else:
            item_name = "Appointment"
            duration = booking.duration_minutes
        
        return {
            'booking_id': str(booking.id),
            'booking_datetime': booking.booking_datetime,
            'item_name': item_name,
            'is_deal_booking': booking.is_deal_booking,
            'service_duration': duration,
            'service_price': booking.total_price,
            'shop_name': booking.shop.name,
            'shop_address': booking.shop.address,
            'shop_phone': booking.shop.phone,
            'staff_name': get_staff_name(booking.staff_member) if booking.staff_member else 'Any available',
            'customer_name': get_customer_name(booking),
        }
