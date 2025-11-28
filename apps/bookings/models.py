"""
Booking model
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils.constants import BOOKING_STATUSES, BOOKING_STATUS_PENDING


class Booking(BaseModel):
    """
    Booking model for appointments
    """
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    
    time_slot = models.OneToOneField(
        'schedules.TimeSlot',
        on_delete=models.PROTECT,
        related_name='booking'
    )
    
    # Booking details
    booking_datetime = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUSES,
        default=BOOKING_STATUS_PENDING,
        db_index=True
    )
    
    # Pricing
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Additional info
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-booking_datetime']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['shop', 'booking_datetime']),
        ]
    
    def __str__(self):
        return f"{self.customer.user.full_name} - {self.service.name} - {self.booking_datetime}"
