"""
API views for notifications management.
"""
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
    MarkNotificationReadSerializer,
    MarkNotificationReadResponseSerializer,
    NotificationCountSerializer,
    DeleteNotificationResponseSerializer,
    TestEmailSerializer,
    TestEmailResponseSerializer,
)


@extend_schema_view(
    get=extend_schema(
        tags=['Notifications'],
        summary='List notifications',
        description='Get all notifications for the current user, ordered by newest first.',
        parameters=[
            OpenApiParameter(
                name='is_read',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by read status (true/false)'
            ),
            OpenApiParameter(
                name='type',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by notification type (e.g., booking_confirmation)'
            ),
        ]
    )
)
class NotificationListView(generics.ListAPIView):
    """
    List all notifications for the authenticated user.
    
    Supports filtering:
    - ?is_read=true/false - Filter by read status
    - ?type=booking_confirmation - Filter by notification type
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by type
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset


@extend_schema(
    tags=['Notifications'],
    summary='Get notification counts',
    description='Get total and unread notification counts for the current user.',
    responses={200: NotificationCountSerializer}
)
class NotificationCountView(views.APIView):
    """Get notification counts for the authenticated user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        counts = Notification.objects.filter(
            user=request.user
        ).aggregate(
            total=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        )
        
        serializer = NotificationCountSerializer(counts)
        return Response(serializer.data)


@extend_schema(
    tags=['Notifications'],
    summary='Mark notifications as read',
    description='Mark specific notifications as read by providing their IDs.',
    request=MarkNotificationReadSerializer,
    responses={200: MarkNotificationReadResponseSerializer}
)
class MarkNotificationReadView(views.APIView):
    """Mark specific notifications as read."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = MarkNotificationReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notification_ids = serializer.validated_data.get('notification_ids', [])
        now = timezone.now()
        
        queryset = Notification.objects.filter(
            user=request.user,
            is_read=False
        )
        
        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        
        updated_count = queryset.update(is_read=True, read_at=now)
        
        response_serializer = MarkNotificationReadResponseSerializer({
            'message': f'{updated_count} notification(s) marked as read',
            'updated_count': updated_count
        })
        return Response(response_serializer.data)


@extend_schema(
    tags=['Notifications'],
    summary='Mark all notifications as read',
    description='Mark all unread notifications as read for the current user.',
    responses={200: MarkNotificationReadResponseSerializer}
)
class MarkAllNotificationsReadView(views.APIView):
    """Mark all notifications as read."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        now = timezone.now()
        
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=now)
        
        response_serializer = MarkNotificationReadResponseSerializer({
            'message': f'{updated_count} notification(s) marked as read',
            'updated_count': updated_count
        })
        return Response(response_serializer.data)


@extend_schema_view(
    get=extend_schema(
        tags=['Notifications'],
        summary='Get notification preferences',
        description='Get the current user\'s email notification preferences.'
    ),
    put=extend_schema(
        tags=['Notifications'],
        summary='Update notification preferences',
        description='Update all notification preferences for the current user.'
    ),
    patch=extend_schema(
        tags=['Notifications'],
        summary='Partially update notification preferences',
        description='Update specific notification preferences. Only send the fields you want to change.'
    )
)
class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    Get or update notification preferences for the authenticated user.
    
    Preferences control which email notifications the user receives:
    - email_booking_confirmation: Booking confirmed emails
    - email_booking_cancellation: Booking cancelled emails
    - email_booking_reschedule: Booking rescheduled emails
    - email_booking_reminder: 1-day and 1-hour reminder emails
    - email_staff_assignment: Staff member changed emails
    - email_shop_holiday: Shop holiday notification emails
    - email_marketing: Marketing and promotional emails
    - push_enabled: In-app push notifications
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        # Get or create preferences for the current user
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences


@extend_schema(
    tags=['Notifications'],
    summary='Delete a notification',
    description='Delete a specific notification by ID.',
    responses={204: None}
)
class NotificationDeleteView(generics.DestroyAPIView):
    """Delete a notification."""
    
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


@extend_schema(
    tags=['Notifications'],
    summary='Clear all notifications',
    description='Delete all notifications for the current user.',
    responses={200: DeleteNotificationResponseSerializer}
)
class ClearAllNotificationsView(views.APIView):
    """Clear all notifications for the user."""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        deleted_count, _ = Notification.objects.filter(
            user=request.user
        ).delete()
        
        response_serializer = DeleteNotificationResponseSerializer({
            'message': f'{deleted_count} notification(s) deleted',
            'deleted_count': deleted_count
        })
        return Response(response_serializer.data)


@extend_schema(
    tags=['Notifications'],
    summary='Send test email',
    description='Send a test email to verify email configuration is working.',
    request=TestEmailSerializer,
    responses={200: TestEmailResponseSerializer}
)
class TestEmailView(views.APIView):
    """Send a test email to verify configuration."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email') or request.user.email
        notification_type = serializer.validated_data.get('notification_type', 'booking_confirmation')
        
        if not email:
            return Response({
                'success': False,
                'message': 'No email address provided and user has no email',
                'email': ''
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subject_map = {
                'booking_confirmation': '✅ Test: Booking Confirmation',
                'booking_reminder': '⏰ Test: Booking Reminder',
                'booking_cancellation': '❌ Test: Booking Cancellation',
            }
            
            subject = subject_map.get(notification_type, 'Test Email from BeautyDrop')
            
            send_mail(
                subject=subject,
                message=f'This is a test email from BeautyDrop.\n\nNotification Type: {notification_type}\nSent to: {email}\nTimestamp: {timezone.now().isoformat()}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
                html_message=f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #8B5CF6;">✨ BeautyDrop Test Email</h1>
                    <p>This is a test email to verify your notification system is working correctly.</p>
                    <div style="background-color: #f8f5ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p><strong>Notification Type:</strong> {notification_type}</p>
                        <p><strong>Sent to:</strong> {email}</p>
                        <p><strong>Timestamp:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    </div>
                    <p style="color: #666;">If you received this email, your Mailgun SMTP configuration is working! 🎉</p>
                </div>
                '''
            )
            
            response_serializer = TestEmailResponseSerializer({
                'success': True,
                'message': f'Test email sent successfully to {email}',
                'email': email
            })
            return Response(response_serializer.data)
            
        except Exception as e:
            response_serializer = TestEmailResponseSerializer({
                'success': False,
                'message': f'Failed to send email: {str(e)}',
                'email': email
            })
            return Response(response_serializer.data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
