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

from .models import CalendarIntegration, CalendarEvent
from .serializers import (
    GoogleConnectSerializer,
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
        description="Receive Google OAuth tokens from Clerk frontend and store them for calendar sync.",
        request=GoogleConnectSerializer,
        responses={
            200: CalendarIntegrationSerializer,
            400: ErrorResponseSerializer,
        },
        tags=['Calendars']
    ),
    google_disconnect=extend_schema(
        summary="Disconnect Google Calendar",
        description="Remove Google Calendar integration and stop syncing bookings.",
        responses={
            200: MessageResponseSerializer,
        },
        tags=['Calendars']
    ),
    status=extend_schema(
        summary="Get Calendar Integration Status",
        description="Get the current user's calendar integration status. Returns default values if no integration exists.",
        responses={
            200: CalendarIntegrationSerializer,
        },
        tags=['Calendars']
    ),
    update_settings=extend_schema(
        summary="Update Calendar Settings",
        description="Update sync preferences like calendar ID and enabled status.",
        request=CalendarSettingsSerializer,
        responses={
            200: CalendarIntegrationSerializer,
        },
        tags=['Calendars']
    ),
    sync=extend_schema(
        summary="Sync All Bookings",
        description="Manually sync all future confirmed bookings to Google Calendar. Returns immediately, sync runs in background.",
        responses={
            202: MessageResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=['Calendars']
    ),
    list_calendars=extend_schema(
        summary="List Google Calendars",
        description="Get list of available Google Calendars for the connected account. Use the 'id' field to update settings.",
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
        Receive Google OAuth tokens from Clerk frontend.
        Frontend gets tokens via Clerk's getOAuthAccessToken("google")
        """
        serializer = GoogleConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        access_token = serializer.validated_data['access_token']
        refresh_token = serializer.validated_data.get('refresh_token', '')
        expires_at = serializer.validated_data.get('expires_at')
        
        # Verify token is valid
        calendar_service = GoogleCalendarService(access_token, refresh_token)
        if not calendar_service.verify_token():
            return Response(
                {'error': 'Invalid Google OAuth token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update integration
        integration, created = CalendarIntegration.objects.update_or_create(
            user=request.user,
            defaults={
                'google_access_token': access_token,
                'google_refresh_token': refresh_token,
                'google_token_expires_at': (
                    datetime.fromtimestamp(expires_at, tz=timezone.utc)
                    if expires_at else None
                ),
            }
        )
        
        logger.info(f"User {request.user.email} connected Google Calendar")
        
        return Response(
            CalendarIntegrationSerializer(integration).data,
            status=status.HTTP_200_OK
        )
    
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
            
            return Response({'message': 'Google Calendar disconnected'})
        
        except CalendarIntegration.DoesNotExist:
            return Response({'message': 'No calendar integration found'})
    
    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        """
        Get calendar integration status for the current user.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            return Response(CalendarIntegrationSerializer(integration).data)
        except CalendarIntegration.DoesNotExist:
            return Response(
                {
                    'is_connected': False,
                    'google_calendar_id': 'primary',
                    'is_sync_enabled': False,
                    'last_sync_at': None
                }
            )
    
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
        
        return Response(CalendarIntegrationSerializer(integration).data)
    
    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        """
        Manually sync all future confirmed bookings to Google Calendar.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            
            if not integration.is_connected:
                return Response(
                    {'error': 'Google Calendar not connected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Queue async task to sync all bookings
            sync_all_bookings_task.delay(str(request.user.id))
            
            return Response(
                {'message': 'Sync started. Bookings will be synced in the background.'},
                status=status.HTTP_202_ACCEPTED
            )
        
        except CalendarIntegration.DoesNotExist:
            return Response(
                {'error': 'No calendar integration found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='calendars')
    def list_calendars(self, request):
        """
        List available Google Calendars for the user.
        Allows them to select which calendar to sync to.
        """
        try:
            integration = CalendarIntegration.objects.get(user=request.user)
            
            if not integration.is_connected:
                return Response(
                    {'error': 'Google Calendar not connected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            calendar_service = GoogleCalendarService(
                integration.google_access_token,
                integration.google_refresh_token
            )
            
            calendars = calendar_service.list_calendars()
            
            return Response(calendars)
        
        except CalendarIntegration.DoesNotExist:
            return Response(
                {'error': 'No calendar integration found'},
                status=status.HTTP_404_NOT_FOUND
            )
