"""
Bookings signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for Booking post-save
    """
    if created:
        # Handle new booking creation
        pass
