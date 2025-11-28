"""
Shops business logic services
"""
from ..models import Shop


class ShopService:
    """
    Service class for Shop business logic
    """
    
    @staticmethod
    def create_shop(data):
        """
        Create a new shop
        """
        return Shop.objects.create(**data)
    
    @staticmethod
    def get_shop_by_id(shop_id):
        """
        Get shop by ID
        """
        try:
            return Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return None
