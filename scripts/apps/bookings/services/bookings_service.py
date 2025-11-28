"""
Bookings business logic services
"""
from ..models import Booking


class BookingService:
    """
    Service class for Booking business logic
    """
    
    @staticmethod
    def create_booking(data):
        """
        Create a new booking
        """
        return Booking.objects.create(**data)
    
    @staticmethod
    def get_booking_by_id(booking_id):
        """
        Get booking by ID
        """
        try:
            return Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return None
