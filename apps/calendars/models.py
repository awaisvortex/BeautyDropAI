"""
Calendar integration models for Google Calendar sync
"""
from django.db import models
from apps.core.models import BaseModel


class CalendarIntegration(BaseModel):
    """
    Stores Google OAuth tokens and calendar settings for each user.
    Tokens are received from the frontend via Clerk OAuth.
    """
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='calendar_integration'
    )
    
    # Google Calendar OAuth tokens (from Clerk frontend)
    google_access_token = models.TextField(blank=True)
    google_refresh_token = models.TextField(blank=True)
    google_token_expires_at = models.DateTimeField(null=True, blank=True)
    google_calendar_id = models.CharField(
        max_length=255,
        default='primary',
        help_text='ID of the Google Calendar to sync events to'
    )
    
    # Sync settings
    is_sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'calendar_integrations'
        verbose_name = 'Calendar Integration'
        verbose_name_plural = 'Calendar Integrations'
    
    def __str__(self):
        return f"Google Calendar - {self.user.email}"
    
    @property
    def is_connected(self):
        """Check if user has connected their Google Calendar"""
        return bool(self.google_access_token)


class CalendarEvent(BaseModel):
    """
    Links bookings to external calendar events for sync tracking.
    Each confirmed booking can have one calendar event per integration (user).
    This allows the same booking to appear in multiple calendars:
    - Customer's calendar
    - Staff member's calendar  
    - Shop owner's (client) calendar
    """
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='calendar_events'
    )
    integration = models.ForeignKey(
        CalendarIntegration,
        on_delete=models.CASCADE,
        related_name='events'
    )
    
    # Google Calendar event ID
    google_event_id = models.CharField(max_length=255, blank=True)
    
    # Sync status
    is_synced = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    
    class Meta:
        db_table = 'calendar_events'
        verbose_name = 'Calendar Event'
        verbose_name_plural = 'Calendar Events'
        # Each booking can only have one event per integration (user)
        unique_together = [['booking', 'integration']]
    
    def __str__(self):
        status = "Synced" if self.is_synced else "Pending"
        return f"{self.booking} - {status}"
