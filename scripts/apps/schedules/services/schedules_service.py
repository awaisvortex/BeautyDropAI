"""
Schedules business logic services
"""
from ..models import ShopSchedule


class ShopScheduleService:
    """
    Service class for ShopSchedule business logic
    """
    
    @staticmethod
    def create_shopschedule(data):
        """
        Create a new shopschedule
        """
        return ShopSchedule.objects.create(**data)
    
    @staticmethod
    def get_shopschedule_by_id(shopschedule_id):
        """
        Get shopschedule by ID
        """
        try:
            return ShopSchedule.objects.get(id=shopschedule_id)
        except ShopSchedule.DoesNotExist:
            return None
