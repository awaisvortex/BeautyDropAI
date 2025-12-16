"""
Serializers for Calendar integration API
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import CalendarIntegration, CalendarEvent


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Connected Calendar',
            summary='User has connected Google Calendar',
            value={
                'is_connected': True,
                'google_calendar_id': 'primary',
                'is_sync_enabled': True,
                'last_sync_at': '2024-12-10T10:30:00Z'
            },
            response_only=True
        ),
        OpenApiExample(
            'Not Connected',
            summary='User has not connected any calendar',
            value={
                'is_connected': False,
                'google_calendar_id': 'primary',
                'is_sync_enabled': False,
                'last_sync_at': None
            },
            response_only=True
        )
    ]
)
class CalendarIntegrationSerializer(serializers.ModelSerializer):
    """
    User's calendar integration status
    """
    is_connected = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CalendarIntegration
        fields = [
            'is_connected',
            'google_calendar_id',
            'is_sync_enabled',
            'last_sync_at'
        ]
        read_only_fields = ['is_connected', 'last_sync_at']


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Update Calendar Settings',
            summary='Change sync settings',
            value={
                'google_calendar_id': 'work@group.calendar.google.com',
                'is_sync_enabled': True
            },
            request_only=True
        ),
        OpenApiExample(
            'Disable Sync',
            summary='Disable automatic syncing',
            value={
                'is_sync_enabled': False
            },
            request_only=True
        )
    ]
)
class CalendarSettingsSerializer(serializers.Serializer):
    """
    Update sync preferences
    """
    google_calendar_id = serializers.CharField(
        required=False,
        max_length=255,
        help_text='ID of the Google Calendar to sync to (default: "primary")'
    )
    is_sync_enabled = serializers.BooleanField(
        required=False,
        help_text='Enable or disable automatic sync'
    )


class CalendarEventSerializer(serializers.ModelSerializer):
    """
    Calendar event details for a booking
    """
    booking_id = serializers.UUIDField(source='booking.id', read_only=True)
    
    class Meta:
        model = CalendarEvent
        fields = [
            'id',
            'booking_id',
            'google_event_id',
            'is_synced',
            'last_synced_at',
            'sync_error'
        ]
        read_only_fields = fields


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Google Calendars List',
            summary='Available calendars for the user',
            value=[
                {
                    'id': 'primary',
                    'summary': 'My Calendar',
                    'primary': True
                },
                {
                    'id': 'work@group.calendar.google.com',
                    'summary': 'Work Calendar',
                    'primary': False
                }
            ],
            response_only=True
        )
    ]
)
class GoogleCalendarListSerializer(serializers.Serializer):
    """
    Response for listing available Google Calendars
    """
    id = serializers.CharField(help_text='Calendar ID to use in settings')
    summary = serializers.CharField(help_text='Human-readable calendar name')
    primary = serializers.BooleanField(help_text='Is this the user\'s primary calendar')


class MessageResponseSerializer(serializers.Serializer):
    """Generic message response"""
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    """Generic error response"""
    error = serializers.CharField()

