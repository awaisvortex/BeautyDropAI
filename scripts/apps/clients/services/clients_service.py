"""
Clients business logic services
"""
from ..models import Client


class ClientService:
    """
    Service class for Client business logic
    """
    
    @staticmethod
    def create_client(data):
        """
        Create a new client
        """
        return Client.objects.create(**data)
    
    @staticmethod
    def get_client_by_id(client_id):
        """
        Get client by ID
        """
        try:
            return Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return None
