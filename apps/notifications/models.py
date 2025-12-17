"""
Notification models for BeautyDropAI.
Includes in-app notifications, email notification logs, FCM devices, and user preferences.
"""
from django.db import models
from apps.core.models import BaseModel


class NotificationType(models.TextChoices):
    """Types of notifications"""
    BOOKING_CONFIRMATION = 'booking_confirmation', 'Booking Confirmation'
    BOOKING_CANCELLATION = 'booking_cancellation', 'Booking Cancellation'
    BOOKING_RESCHEDULE = 'booking_reschedule', 'Booking Rescheduled'
    BOOKING_REMINDER_1DAY = 'booking_reminder_1day', 'Booking Reminder (1 Day)'
    BOOKING_REMINDER_1HOUR = 'booking_reminder_1hour', 'Booking Reminder (1 Hour)'
    STAFF_ASSIGNMENT = 'staff_assignment', 'Staff Assignment Changed'
    SHOP_HOLIDAY = 'shop_holiday', 'Shop Holiday'
    NEW_BOOKING = 'new_booking', 'New Booking (for staff/client)'
    PAYMENT_SUCCESS = 'payment_success', 'Payment Successful'
    PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
    SYSTEM = 'system', 'System Notification'
    PAYMENT = 'payment', 'Payment Notification'


class NotificationStatus(models.TextChoices):
    """Status of email notifications"""
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    DELIVERED = 'delivered', 'Delivered'
    FAILED = 'failed', 'Failed'
    BOUNCED = 'bounced', 'Bounced'



class Notification(BaseModel):
    """
    In-app notification model for user notifications.
    These are displayed in the app's notification center.
    """
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        to_field='clerk_user_id'
    )
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Type
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related objects (optional)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class EmailNotificationLog(BaseModel):
    """
    Tracks all sent email notifications for auditing and debugging.
    Stores Mailgun message IDs for tracking delivery status.
    """
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='email_logs',
        null=True,
        blank=True,
        help_text='Related in-app notification if exists'
    )
    
    # Email details
    email_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        db_index=True
    )
    recipient_email = models.EmailField(db_index=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True
    )
    
    # Mailgun tracking
    mailgun_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Related booking for reminder deduplication
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='email_logs',
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'email_notification_logs'
        verbose_name = 'Email Notification Log'
        verbose_name_plural = 'Email Notification Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email_type', 'status']),
            models.Index(fields=['booking', 'email_type']),
        ]
        # Prevent duplicate reminders for the same booking and type
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'email_type', 'recipient_email'],
                name='unique_booking_email_notification',
                condition=models.Q(booking__isnull=False)
            )
        ]
    
    def __str__(self):
        return f"{self.email_type} to {self.recipient_email} - {self.status}"


class NotificationPreference(BaseModel):
    """
    User preferences for notification opt-out.
    By default, all notifications are enabled.
    Users can disable specific notification types.
    """
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        to_field='clerk_user_id'
    )
    
    # Email notification preferences (True = enabled)
    email_booking_confirmation = models.BooleanField(
        default=True,
        help_text='Receive email when booking is confirmed'
    )
    email_booking_cancellation = models.BooleanField(
        default=True,
        help_text='Receive email when booking is cancelled'
    )
    email_booking_reschedule = models.BooleanField(
        default=True,
        help_text='Receive email when booking is rescheduled'
    )
    email_booking_reminder = models.BooleanField(
        default=True,
        help_text='Receive reminder emails before appointments'
    )
    email_staff_assignment = models.BooleanField(
        default=True,
        help_text='Receive email when staff member is changed'
    )
    email_shop_holiday = models.BooleanField(
        default=True,
        help_text='Receive email about shop holiday closures'
    )
    email_marketing = models.BooleanField(
        default=False,
        help_text='Receive marketing and promotional emails'
    )
    
    # In-app notification preferences
    push_enabled = models.BooleanField(
        default=True,
        help_text='Enable in-app notifications'
    )
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
    
    def is_email_enabled(self, notification_type: str) -> bool:
        """
        Check if email notifications are enabled for a specific type.
        
        Args:
            notification_type: The NotificationType value
            
        Returns:
            bool: True if the notification type is enabled
        """
        type_mapping = {
            NotificationType.BOOKING_CONFIRMATION: self.email_booking_confirmation,
            NotificationType.BOOKING_CANCELLATION: self.email_booking_cancellation,
            NotificationType.BOOKING_RESCHEDULE: self.email_booking_reschedule,
            NotificationType.BOOKING_REMINDER_1DAY: self.email_booking_reminder,
            NotificationType.BOOKING_REMINDER_1HOUR: self.email_booking_reminder,
            NotificationType.STAFF_ASSIGNMENT: self.email_staff_assignment,
            NotificationType.SHOP_HOLIDAY: self.email_shop_holiday,
        }
        return type_mapping.get(notification_type, True)


class DeviceType(models.TextChoices):
    """Types of devices for FCM"""
    IOS = 'ios', 'iOS'
    ANDROID = 'android', 'Android'
    WEB = 'web', 'Web'


class FCMDevice(BaseModel):
    """
    Stores Firebase Cloud Messaging device tokens for push notifications.
    Each user can have multiple devices registered.
    """
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='fcm_devices',
        to_field='clerk_user_id'
    )
    
    # FCM registration token from the device
    fcm_token = models.CharField(
        max_length=500,
        unique=True,
        help_text='Firebase Cloud Messaging device token'
    )
    
    # Device info
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.WEB
    )
    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Optional device name for identification'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Set to False if token is invalid or unregistered'
    )
    
    class Meta:
        db_table = 'fcm_devices'
        verbose_name = 'FCM Device'
        verbose_name_plural = 'FCM Devices'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.device_type} ({self.fcm_token[:20]}...)"
