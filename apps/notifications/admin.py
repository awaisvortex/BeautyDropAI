"""
Admin configuration for notifications app.
"""
from django.contrib import admin
from apps.notifications.models import (
    Notification,
    EmailNotificationLog,
    NotificationPreference
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for in-app notifications."""
    list_display = [
        'id', 'user', 'title', 'notification_type',
        'is_read', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(EmailNotificationLog)
class EmailNotificationLogAdmin(admin.ModelAdmin):
    """Admin for email notification logs."""
    list_display = [
        'id', 'email_type', 'recipient_email', 'status',
        'sent_at', 'created_at'
    ]
    list_filter = ['email_type', 'status', 'created_at']
    search_fields = ['recipient_email', 'subject', 'mailgun_message_id']
    readonly_fields = [
        'created_at', 'updated_at', 'sent_at',
        'delivered_at', 'mailgun_message_id'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Email Details', {
            'fields': ('email_type', 'recipient_email', 'recipient_name', 'subject')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'retry_count')
        }),
        ('Tracking', {
            'fields': ('mailgun_message_id', 'sent_at', 'delivered_at')
        }),
        ('Related Objects', {
            'fields': ('notification', 'booking'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin for user notification preferences."""
    list_display = [
        'id', 'user', 'email_booking_confirmation',
        'email_booking_reminder', 'push_enabled'
    ]
    list_filter = [
        'email_booking_confirmation', 'email_booking_reminder',
        'email_marketing', 'push_enabled'
    ]
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Booking Notifications', {
            'fields': (
                'email_booking_confirmation',
                'email_booking_cancellation',
                'email_booking_reschedule',
                'email_booking_reminder',
            )
        }),
        ('Other Notifications', {
            'fields': (
                'email_staff_assignment',
                'email_shop_holiday',
                'email_marketing',
            )
        }),
        ('Push Notifications', {
            'fields': ('push_enabled',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
