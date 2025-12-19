"""
Firebase Cloud Messaging (FCM) service for push notifications.
Handles sending notifications to users' devices via Firebase.
"""
import logging
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)

# Firebase Admin SDK initialization
_firebase_app = None


def get_firebase_app():
    """
    Initialize and return the Firebase app.
    Lazy initialization to avoid startup issues.
    """
    global _firebase_app
    
    if _firebase_app is not None:
        return _firebase_app
    
    try:
        import firebase_admin
        from firebase_admin import credentials
        
        # Check if already initialized
        try:
            _firebase_app = firebase_admin.get_app()
            return _firebase_app
        except ValueError:
            pass  # App not initialized yet
        
        # Initialize with credentials
        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        
        if cred_path:
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            # Try to use default credentials (for Cloud Run with attached service account)
            _firebase_app = firebase_admin.initialize_app()
        
        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None


class FCMService:
    """
    Service class for sending Firebase Cloud Messaging notifications.
    """
    
    @classmethod
    def send_to_user(
        cls,
        user,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_type: str = 'system'
    ) -> int:
        """
        Send push notification to all of a user's registered devices.
        Also creates a Notification record in the database.
        
        Args:
            user: User instance
            title: Notification title
            body: Notification body text
            data: Optional data payload (must be string key-value pairs)
            notification_type: Type of notification for analytics
            
        Returns:
            Number of notifications sent successfully
        """
        from apps.notifications.models import FCMDevice, Notification
        
        # Create database notification for history
        try:
            Notification.objects.create(
                user=user,
                title=title,
                message=body,
                notification_type=notification_type,
                metadata=data or {}
            )
        except Exception as e:
            logger.error(f"Failed to create notification record: {e}")
        
        # Get all active devices for the user
        devices = FCMDevice.objects.filter(
            user=user,
            is_active=True
        )
        
        if not devices.exists():
            logger.debug(f"No active FCM devices for user {user.email}")
            return 0
        
        tokens = list(devices.values_list('fcm_token', flat=True))
        
        success_count = 0
        failed_tokens = []
        
        for token in tokens:
            success = cls.send_to_token(
                token=token,
                title=title,
                body=body,
                data=data
            )
            if success:
                success_count += 1
            else:
                failed_tokens.append(token)
        
        # Deactivate failed tokens
        if failed_tokens:
            FCMDevice.objects.filter(fcm_token__in=failed_tokens).update(is_active=False)
            logger.info(f"Deactivated {len(failed_tokens)} invalid FCM tokens for user {user.email}")
        
        logger.info(f"Sent {success_count}/{len(tokens)} push notifications to user {user.email}")
        return success_count
    
    @classmethod
    def send_to_token(
        cls,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send push notification to a specific device token.
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body text
            data: Optional data payload
            
        Returns:
            True if sent successfully, False otherwise
        """
        app = get_firebase_app()
        if app is None:
            logger.warning("Firebase not initialized, skipping push notification")
            return False
        
        try:
            from firebase_admin import messaging
            
            # Build the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
                # Android specific config
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='notification_icon',
                        color='#8B5CF6',  # BeautyDrop brand color
                        click_action='FLUTTER_NOTIFICATION_CLICK',
                    ),
                ),
                # iOS specific config
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            badge=1,
                            sound='default',
                        ),
                    ),
                ),
                # Web specific config
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        icon='/icons/notification-icon.png',
                    ),
                ),
            )
            
            # Send the message
            response = messaging.send(message)
            logger.debug(f"FCM message sent successfully: {response}")
            return True
            
        except Exception as e:
            error_str = str(e)
            
            # Check if token is invalid/expired
            if 'UNREGISTERED' in error_str or 'INVALID_ARGUMENT' in error_str:
                logger.warning(f"Invalid FCM token: {token[:20]}...")
                return False
            
            logger.error(f"Failed to send FCM message: {e}")
            return False
    
    @classmethod
    def send_to_multiple_users(
        cls,
        users: List,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_type: str = 'system'
    ) -> int:
        """
        Send push notification to multiple users.
        
        Args:
            users: List of User instances
            title: Notification title
            body: Notification body text
            data: Optional data payload
            notification_type: Type of notification
            
        Returns:
            Total number of notifications sent successfully
        """
        total_sent = 0
        for user in users:
            sent = cls.send_to_user(
                user=user,
                title=title,
                body=body,
                data=data,
                notification_type=notification_type
            )
            total_sent += sent
        return total_sent
    
    @classmethod
    def send_booking_notification(
        cls,
        user,
        booking,
        notification_type: str,
        title: str,
        body: str
    ) -> bool:
        """
        Send a booking-related push notification.
        
        Args:
            user: User to notify
            booking: Booking instance
            notification_type: NotificationType value
            title: Notification title
            body: Notification body
            
        Returns:
            True if at least one notification was sent
        """
        data = {
            'type': notification_type,
            'booking_id': str(booking.id),
            'shop_id': str(booking.shop.id),
            'service_name': booking.service.name,
        }
        
        sent = cls.send_to_user(
            user=user,
            title=title,
            body=body,
            data=data,
            notification_type=notification_type
        )
        
        return sent > 0
