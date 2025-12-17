"""
Serializers for notifications API.
With Firebase Cloud Messaging support.
"""
from rest_framework import serializers
from apps.notifications.models import (
    Notification,
    NotificationPreference,
    EmailNotificationLog,
    NotificationType,
    NotificationStatus,
    FCMDevice,
    DeviceType
)


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for in-app notifications."""
    
    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True,
        help_text='Human-readable notification type'
    )
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'notification_type',
            'notification_type_display',
            'is_read',
            'read_at',
            'related_object_type',
            'related_object_id',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'id', 'title', 'message', 'notification_type',
            'related_object_type', 'related_object_id',
            'metadata', 'created_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user notification preferences."""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'email_booking_confirmation',
            'email_booking_cancellation',
            'email_booking_reschedule',
            'email_booking_reminder',
            'email_staff_assignment',
            'email_shop_holiday',
            'email_marketing',
            'push_enabled',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']
        extra_kwargs = {
            'email_booking_confirmation': {'help_text': 'Receive email when booking is confirmed'},
            'email_booking_cancellation': {'help_text': 'Receive email when booking is cancelled'},
            'email_booking_reschedule': {'help_text': 'Receive email when booking is rescheduled'},
            'email_booking_reminder': {'help_text': 'Receive reminder emails before appointments'},
            'email_staff_assignment': {'help_text': 'Receive email when staff member is changed'},
            'email_shop_holiday': {'help_text': 'Receive email about shop holiday closures'},
            'email_marketing': {'help_text': 'Receive marketing and promotional emails'},
            'push_enabled': {'help_text': 'Enable in-app push notifications'},
        }


class MarkNotificationReadSerializer(serializers.Serializer):
    """Input serializer for marking notifications as read."""
    
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text='List of notification IDs to mark as read. If empty or not provided, marks all as read.'
    )


class MarkNotificationReadResponseSerializer(serializers.Serializer):
    """Response serializer for marking notifications as read."""
    
    message = serializers.CharField(help_text='Success message')
    updated_count = serializers.IntegerField(help_text='Number of notifications marked as read')


class NotificationCountSerializer(serializers.Serializer):
    """Serializer for notification counts."""
    
    total = serializers.IntegerField(help_text='Total number of notifications')
    unread = serializers.IntegerField(help_text='Number of unread notifications')


class DeleteNotificationResponseSerializer(serializers.Serializer):
    """Response serializer for deleting notifications."""
    
    message = serializers.CharField(help_text='Success message')
    deleted_count = serializers.IntegerField(help_text='Number of notifications deleted')


class EmailNotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for email notification logs (admin use)."""
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    email_type_display = serializers.CharField(
        source='get_email_type_display',
        read_only=True
    )
    
    class Meta:
        model = EmailNotificationLog
        fields = [
            'id',
            'email_type',
            'email_type_display',
            'recipient_email',
            'subject',
            'status',
            'status_display',
            'sent_at',
            'created_at',
        ]
        read_only_fields = fields


class TestEmailSerializer(serializers.Serializer):
    """Input serializer for sending test emails."""
    
    email = serializers.EmailField(
        required=False,
        help_text='Email address to send test to. Defaults to current user email.'
    )
    notification_type = serializers.ChoiceField(
        choices=[
            ('booking_confirmation', 'Booking Confirmation'),
            ('booking_reminder', 'Booking Reminder'),
            ('booking_cancellation', 'Booking Cancellation'),
        ],
        default='booking_confirmation',
        help_text='Type of test email to send'
    )


class TestEmailResponseSerializer(serializers.Serializer):
    """Response serializer for test email."""
    
    success = serializers.BooleanField(help_text='Whether the email was sent successfully')
    message = serializers.CharField(help_text='Result message')
    email = serializers.EmailField(help_text='Email address sent to')


class FCMTokenSerializer(serializers.Serializer):
    """Input serializer for registering FCM device tokens."""
    
    fcm_token = serializers.CharField(
        max_length=500,
        help_text='Firebase Cloud Messaging device token'
    )
    device_type = serializers.ChoiceField(
        choices=DeviceType.choices,
        default=DeviceType.WEB,
        required=False,
        help_text='Type of device (ios, android, web)'
    )
    device_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text='Optional device name for identification (e.g., "iPhone 15 Pro")'
    )


class FCMTokenResponseSerializer(serializers.Serializer):
    """Response serializer for FCM token operations."""
    
    message = serializers.CharField(help_text='Operation result message')
    device_id = serializers.CharField(help_text='ID of the registered device')
    is_new = serializers.BooleanField(help_text='True if this is a new registration')


class FCMDeviceSerializer(serializers.ModelSerializer):
    """Serializer for FCM device details (admin use)."""
    
    device_type_display = serializers.CharField(
        source='get_device_type_display',
        read_only=True
    )
    
    class Meta:
        model = FCMDevice
        fields = [
            'id',
            'fcm_token',
            'device_type',
            'device_type_display',
            'device_name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
