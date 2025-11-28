"""
Notifications business logic services
"""
from ..models import Notification


class NotificationService:
    """
    Service class for Notification business logic
    """
    
    @staticmethod
    def create_notification(data):
        """
        Create a new notification
        """
        return Notification.objects.create(**data)
    
    @staticmethod
    def get_notification_by_id(notification_id):
        """
        Get notification by ID
        """
        try:
            return Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return None
