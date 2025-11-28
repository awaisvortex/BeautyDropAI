"""
Subscriptions business logic services
"""
from ..models import Subscription


class SubscriptionService:
    """
    Service class for Subscription business logic
    """
    
    @staticmethod
    def create_subscription(data):
        """
        Create a new subscription
        """
        return Subscription.objects.create(**data)
    
    @staticmethod
    def get_subscription_by_id(subscription_id):
        """
        Get subscription by ID
        """
        try:
            return Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return None
