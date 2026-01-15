"""
Views for Calendar integration API
"""
import logging
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from apps.core.messages import CALENDAR
from .models import CalendarIntegration, CalendarEvent
from .serializers import (
    CalendarIntegrationSerializer,
    CalendarSettingsSerializer,
    GoogleCalendarListSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
)
from .google_calendar_service import GoogleCalendarService
from .tasks import sync_all_bookings_task

logger = logging.getLogger(__name__)


@extend_schema_view(
    google_connect=extend_schema(
        summary="Connect Google Calendar",
        description="""
        Connect Google Calendar using OAuth tokens fetched automatically from Clerk.
        
        **Prerequisites:**
        - You must be signed in with Google via Clerk SSO
        - Calendar permissions must be granted during sign-in
        
        **If connection fails:**
        - Sign out and sign back in using Google
        - Make sure to allow calendar access when prompted
        """,
        request=None,
        responses={
            200: CalendarIntegrationSerializer,
            400: ErrorResponseSerializer,
        },
        tags=['Calendars']
    ),

    google_disconnect=extend_schema(
        summary="Disconnect Google Calendar",
        description="Remove Google Calendar integration and stop syncing bookings. Your calendar events created by this app will remain.",
        responses={
            200: MessageResponseSerializer,
        },
        tags=['Calendars']
    ),
    status=extend_schema(
        summary="Get Calendar Integration Status",
        description="Get the current user's calendar integration status. Check if Google Calendar is connected and syncing.",
        responses={
            200: CalendarIntegrationSerializer,
        },
        tags=['Calendars']
    ),
    update_settings=extend_schema(
        summary="Update Calendar Settings",
        description="Update sync preferences like which calendar to sync to and whether sync is enabled.",
        request=CalendarSettingsSerializer,
        responses={
            200: CalendarIntegrationSerializer,
        },
        tags=['Calendars']
    ),
    sync=extend_schema(
        summary="Sync All Bookings",
        description="Manually sync all future confirmed bookings to Google Calendar. The sync runs in the background - you'll see events appear within a few minutes.",
        responses={
            202: MessageResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=['Calendars']
    ),
    list_calendars=extend_schema(
        summary="List Google Calendars",
        description="Get list of available Google Calendars. Use this to let users choose which calendar to sync bookings to. The 'id' field is what you pass to update_settings.",
        responses={
            200: GoogleCalendarListSerializer(many=True),
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=['Calendars']
    ),
)
class CalendarViewSet(ViewSet):
    """
    ViewSet for managing Google Calendar integration.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='google/connect')
    def google_connect(self, request):
        """
        Connect Google Calendar by fetching OAuth token from Clerk.
        User must have connected Google via Clerk SSO with calendar scope.
        """
        from apps.authentication.services.clerk_service import clerk_service
        
        # Get Google OAuth token from Clerk
        token_data = clerk_service.get_google_oauth_token(request.user.clerk_user_id)
        
        logger.info(f"Clerk token response for {request.user.email}: {token_data}")
        
        if not token_data or not token_data.get('token'):
            return Response(
                CALENDAR['not_connected_clerk'],
                status=status.HTTP_400_BAD_REQUEST
            )
        
        access_token = token_data['token']
        scopes = token_data.get('scopes', [])
        
        logger.info(f"Token scopes for {request.user.email}: {scopes}")
        
        # Check if calendar scope is present
        calendar_scope = 'https://www.googleapis.com/auth/calendar.events'
        if calendar_scope not in scopes:
            return Response(
                CALENDAR['missing_calendar_permission'],
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify token works with Google Calendar API
        calendar_service = GoogleCalendarService(access_token)
        if not calendar_service.verify_token():
            return Response(
                CALENDAR['api_verification_failed'],
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update integration
        # Note: We don't store the token since Clerk manages refresh automatically
        # We'll fetch fresh tokens from Clerk each time we need to sync
        integration, created = CalendarIntegration.objects.update_or_create(
            user=request.user,
            defaults={
                'google_access_token': access_token,
                'google_refresh_token': '',  # Clerk manages refresh
                'google_token_expires_at': None,  # Clerk manages expiry
            }
        )
        
        logger.info(f"User {request.user.email} connected Google Calendar via Clerk")
        
        response_data = CalendarIntegrationSerializer(integration).data
        response_data['message'] = "Google Calendar connected successfully! Your bookings will now sync automatically."
        response_data['next_steps'] = "You can choose which calendar to sync to in the settings."
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='google/disconnect')
    def google_disconnect(self, request):
        """
        Disconnect Google Calendar integration.
        Removes stored tokens and stops syncing.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            
            # Clear tokens but keep the record for settings
            integration.google_access_token = ''
            integration.google_refresh_token = ''
            integration.google_token_expires_at = None
            integration.save()
            
            # Optionally delete all calendar events for this integration
            CalendarEvent.objects.filter(integration=integration).delete()
            
            logger.info(f"User {request.user.email} disconnected Google Calendar")
            
            return Response({
                'message': 'Google Calendar disconnected successfully.',
                'next_steps': 'Your existing calendar events will remain. New bookings will not be synced.'
            })
        
        except CalendarIntegration.DoesNotExist:
            return Response({
                'message': 'No calendar was connected.',
                'next_steps': 'Nothing to disconnect.'
            })
    
    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        """
        Get calendar integration status for the current user.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            data = CalendarIntegrationSerializer(integration).data
            
            # Add helpful status message
            if integration.is_connected:
                data['message'] = "Google Calendar is connected and syncing your bookings."
            else:
                data['message'] = "Google Calendar was disconnected. Connect again to resume syncing."
                data['next_steps'] = "Click 'Connect Google Calendar' to start syncing."
            
            return Response(data)
        except CalendarIntegration.DoesNotExist:
            return Response({
                'is_connected': False,
                'google_calendar_id': 'primary',
                'is_sync_enabled': False,
                'last_sync_at': None,
                'message': "Google Calendar is not connected yet.",
                'next_steps': "Connect your Google Calendar to automatically sync all your bookings."
            })
    
    @action(detail=False, methods=['patch'], url_path='settings')
    def update_settings(self, request):
        """
        Update sync preferences.
        """
        serializer = CalendarSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        integration, _ = CalendarIntegration.objects.get_or_create(
            user=request.user,
            defaults={'is_sync_enabled': True}
        )
        
        if 'google_calendar_id' in serializer.validated_data:
            integration.google_calendar_id = serializer.validated_data['google_calendar_id']
        
        if 'is_sync_enabled' in serializer.validated_data:
            integration.is_sync_enabled = serializer.validated_data['is_sync_enabled']
        
        integration.save()
        
        data = CalendarIntegrationSerializer(integration).data
        data['message'] = "Calendar settings updated successfully."
        
        return Response(data)
    
    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        """
        Manually sync all future confirmed bookings to Google Calendar.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            
            if not integration.is_connected:
                return Response(
                    CALENDAR['not_connected'],
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Queue async task to sync all bookings
            sync_all_bookings_task.delay(request.user.clerk_user_id)
            
            return Response({
                'message': 'Syncing your bookings to Google Calendar...',
                'next_steps': 'Your bookings will appear in your calendar within a few minutes.'
            }, status=status.HTTP_202_ACCEPTED)
        
        except CalendarIntegration.DoesNotExist:
            return Response(
                CALENDAR['no_integration'],
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='calendars')
    def list_calendars(self, request):
        """
        List available Google Calendars for the user.
        Allows them to select which calendar to sync to.
        """
        from apps.authentication.services.clerk_service import clerk_service
        
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            
            if not integration.is_connected:
                return Response(
                    CALENDAR['not_connected'],
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch fresh token from Clerk
            token_data = clerk_service.get_google_oauth_token(request.user.clerk_user_id)
            if not token_data or not token_data.get('token'):
                return Response(
                    CALENDAR['token_refresh_failed'],
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            calendar_service = GoogleCalendarService(token_data['token'])
            
            calendars = calendar_service.list_calendars()
            
            return Response({
                'calendars': calendars,
                'message': "Choose which calendar to sync your bookings to.",
                'current_calendar': integration.google_calendar_id
            })
        
        except CalendarIntegration.DoesNotExist:
            return Response(
                CALENDAR['no_integration'],
                status=status.HTTP_404_NOT_FOUND
            )
