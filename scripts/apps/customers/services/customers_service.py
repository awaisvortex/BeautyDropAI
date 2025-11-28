"""
Customers business logic services
"""
from ..models import Customer


class CustomerService:
    """
    Service class for Customer business logic
    """
    
    @staticmethod
    def create_customer(data):
        """
        Create a new customer
        """
        return Customer.objects.create(**data)
    
    @staticmethod
    def get_customer_by_id(customer_id):
        """
        Get customer by ID
        """
        try:
            return Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return None
