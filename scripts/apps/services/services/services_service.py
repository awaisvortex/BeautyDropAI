"""
Services business logic services
"""
from ..models import Service


class ServiceService:
    """
    Service class for Service business logic
    """
    
    @staticmethod
    def create_service(data):
        """
        Create a new service
        """
        return Service.objects.create(**data)
    
    @staticmethod
    def get_service_by_id(service_id):
        """
        Get service by ID
        """
        try:
            return Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            return None
