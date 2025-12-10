"""
Google Calendar Service for calendar integration.
Uses Google Calendar API with OAuth tokens from Clerk.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """
    Service class for Google Calendar API operations.
    OAuth authentication is handled by Clerk on the frontend.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    
    def __init__(self, access_token: str, refresh_token: str = None):
        """
        Initialize with OAuth tokens from Clerk.
        
        Args:
            access_token: Google OAuth access token
            refresh_token: Google OAuth refresh token (optional)
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._service = None
    
    def _build_service(self):
        """
        Build the Google Calendar API service.
        """
        if self._service is None:
            credentials = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
            )
            self._service = build('calendar', 'v3', credentials=credentials)
        return self._service
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars available to the user.
        
        Returns:
            List of calendars with id, summary, and primary flag
        """
        try:
            service = self._build_service()
            calendar_list = service.calendarList().list().execute()
            
            calendars = []
            for calendar in calendar_list.get('items', []):
                calendars.append({
                    'id': calendar['id'],
                    'summary': calendar.get('summary', 'Untitled'),
                    'primary': calendar.get('primary', False)
                })
            
            return calendars
        except HttpError as e:
            logger.error(f"Failed to list calendars: {e}")
            raise
    
    def create_booking_event(
        self,
        booking,
        calendar_id: str = 'primary'
    ) -> Optional[str]:
        """
        Create a calendar event for a booking.
        
        Args:
            booking: Booking model instance
            calendar_id: Google Calendar ID (default: 'primary')
        
        Returns:
            Google Calendar event ID or None on failure
        """
        try:
            service = self._build_service()
            
            # Calculate end time based on service duration
            start_time = booking.booking_datetime
            end_time = start_time + timedelta(minutes=booking.service.duration_minutes)
            
            # Build event body
            event = {
                'summary': f"{booking.service.name} - {booking.shop.name}",
                'description': self._build_event_description(booking),
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(booking.shop.timezone) if hasattr(booking.shop, 'timezone') else 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(booking.shop.timezone) if hasattr(booking.shop, 'timezone') else 'UTC',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 60},  # 1 hour before
                        {'method': 'popup', 'minutes': 15},  # 15 minutes before
                    ],
                },
            }
            
            # Add location if shop has address
            if hasattr(booking.shop, 'address') and booking.shop.address:
                event['location'] = booking.shop.address
            
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info(f"Created calendar event {created_event['id']} for booking {booking.id}")
            return created_event['id']
            
        except HttpError as e:
            logger.error(f"Failed to create calendar event for booking {booking.id}: {e}")
            raise
    
    def update_booking_event(
        self,
        event_id: str,
        booking,
        calendar_id: str = 'primary'
    ) -> bool:
        """
        Update an existing calendar event (e.g., when booking is rescheduled).
        
        Args:
            event_id: Google Calendar event ID
            booking: Updated Booking model instance
            calendar_id: Google Calendar ID
        
        Returns:
            True on success, False on failure
        """
        try:
            service = self._build_service()
            
            # Calculate end time
            start_time = booking.booking_datetime
            end_time = start_time + timedelta(minutes=booking.service.duration_minutes)
            
            event = {
                'summary': f"{booking.service.name} - {booking.shop.name}",
                'description': self._build_event_description(booking),
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(booking.shop.timezone) if hasattr(booking.shop, 'timezone') else 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(booking.shop.timezone) if hasattr(booking.shop, 'timezone') else 'UTC',
                },
            }
            
            service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"Updated calendar event {event_id} for booking {booking.id}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to update calendar event {event_id}: {e}")
            raise
    
    def delete_booking_event(
        self,
        event_id: str,
        calendar_id: str = 'primary'
    ) -> bool:
        """
        Delete a calendar event (e.g., when booking is cancelled).
        
        Args:
            event_id: Google Calendar event ID
            calendar_id: Google Calendar ID
        
        Returns:
            True on success, False on failure
        """
        try:
            service = self._build_service()
            
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Deleted calendar event {event_id}")
            return True
            
        except HttpError as e:
            # 404 is OK - event may have been deleted externally
            if e.resp.status == 404:
                logger.warning(f"Calendar event {event_id} not found (already deleted)")
                return True
            logger.error(f"Failed to delete calendar event {event_id}: {e}")
            raise
    
    def _build_event_description(self, booking) -> str:
        """
        Build a formatted description for the calendar event.
        """
        lines = [
            f"Service: {booking.service.name}",
            f"Shop: {booking.shop.name}",
            f"Price: ${booking.total_price}",
        ]
        
        if booking.staff_member:
            lines.append(f"Staff: {booking.staff_member.user.full_name}")
        
        if booking.notes:
            lines.append(f"\nNotes: {booking.notes}")
        
        lines.append(f"\nBooking ID: {booking.id}")
        
        return "\n".join(lines)
    
    def verify_token(self) -> bool:
        """
        Verify that the access token is valid by making a simple API call.
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            service = self._build_service()
            # Simple call to verify authentication
            service.calendarList().list(maxResults=1).execute()
            return True
        except HttpError as e:
            logger.error(f"Token verification failed: {e}")
            return False
