"""
API views for notifications management.
With Firebase Cloud Messaging integration.
"""
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from apps.notifications.models import NotificationPreference, FCMDevice, DeviceType
from apps.notifications.serializers import (
    NotificationPreferenceSerializer,
    FCMTokenSerializer,
    FCMTokenResponseSerializer,
    TestEmailSerializer,
    TestEmailResponseSerializer,
)


@extend_schema(
    tags=['Notifications'],
    summary='Register FCM device token',
    description='''
    Register a Firebase Cloud Messaging device token for push notifications.
    
    The frontend should call this endpoint:
    - After user login
    - When the FCM token refreshes
    - When the app gains notification permissions
    
    If the token already exists for a different user, it will be reassigned to the current user.
    ''',
    request=FCMTokenSerializer,
    responses={
        200: FCMTokenResponseSerializer,
        201: FCMTokenResponseSerializer,
    }
)
class FCMTokenView(views.APIView):
    """
    Register or unregister FCM device tokens for push notifications.
    
    POST: Register a new device token
    DELETE: Unregister a device token (when user logs out or disables notifications)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Register a new FCM device token."""
        serializer = FCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        fcm_token = serializer.validated_data['fcm_token']
        device_type = serializer.validated_data.get('device_type', DeviceType.WEB)
        device_name = serializer.validated_data.get('device_name', '')
        
        # Check if token already exists
        existing_device = FCMDevice.objects.filter(fcm_token=fcm_token).first()
        
        if existing_device:
            # Token exists - update it (might be different user or reactivation)
            existing_device.user = request.user
            existing_device.device_type = device_type
            existing_device.device_name = device_name
            existing_device.is_active = True
            existing_device.save()
            
            response_serializer = FCMTokenResponseSerializer({
                'message': 'FCM token updated successfully',
                'device_id': str(existing_device.id),
                'is_new': False
            })
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            # Create new device registration
            device = FCMDevice.objects.create(
                user=request.user,
                fcm_token=fcm_token,
                device_type=device_type,
                device_name=device_name
            )
            
            response_serializer = FCMTokenResponseSerializer({
                'message': 'FCM token registered successfully',
                'device_id': str(device.id),
                'is_new': True
            })
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        tags=['Notifications'],
        summary='Unregister FCM device token',
        description='Remove a device token when user logs out or disables notifications.',
        request=FCMTokenSerializer,
        responses={200: FCMTokenResponseSerializer}
    )
    def delete(self, request):
        """Unregister an FCM device token."""
        serializer = FCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        fcm_token = serializer.validated_data['fcm_token']
        
        # Find and deactivate or delete the device
        deleted_count, _ = FCMDevice.objects.filter(
            user=request.user,
            fcm_token=fcm_token
        ).delete()
        
        if deleted_count > 0:
            response_serializer = FCMTokenResponseSerializer({
                'message': 'FCM token unregistered successfully',
                'device_id': '',
                'is_new': False
            })
        else:
            response_serializer = FCMTokenResponseSerializer({
                'message': 'FCM token not found',
                'device_id': '',
                'is_new': False
            })
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=['Notifications'],
        summary='Get notification preferences',
        description='Get the current user\'s email and push notification preferences.'
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
    
    Preferences control which notifications the user receives:
    - email_booking_confirmation: Booking confirmed emails
    - email_booking_cancellation: Booking cancelled emails
    - email_booking_reschedule: Booking rescheduled emails
    - email_booking_reminder: 1-day and 1-hour reminder emails
    - email_staff_assignment: Staff member changed emails
    - email_shop_holiday: Shop holiday notification emails
    - email_marketing: Marketing and promotional emails
    - push_enabled: In-app push notifications via Firebase
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
