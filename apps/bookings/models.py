"""
Booking model
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils.constants import (
    BOOKING_STATUSES, BOOKING_STATUS_PENDING,
    BOOKING_PAYMENT_STATUSES, BOOKING_PAYMENT_PENDING
)


class Booking(BaseModel):
    """
    Booking model for appointments.
    
    A booking is either for a SERVICE or a DEAL (mutually exclusive).
    - Service bookings require staff assignment
    - Deal bookings do NOT require staff (just time slot based on shop capacity)
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text='Service booked (NULL for deal bookings or if service was deleted)'
    )
    
    deal = models.ForeignKey(
        'services.Deal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text='Deal/package booked (NULL for service bookings)'
    )
    
    time_slot = models.OneToOneField(
        'schedules.TimeSlot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking',
        help_text='Optional: Only set for bookings created from pre-generated TimeSlots'
    )
    
    staff_member = models.ForeignKey(
        'staff.StaffMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text='Staff member assigned to this booking (NULL for deal bookings)'
    )
    
    # Booking details
    booking_datetime = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text='Duration of the booking in minutes (from service or deal duration)'
    )
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
    cancelled_by = models.CharField(
        max_length=20,
        choices=[
            ('customer', 'Customer'),
            ('staff', 'Staff'),
            ('owner', 'Owner'),
            ('system', 'System'),
        ],
        blank=True,
        null=True,
        help_text='Who cancelled the booking'
    )
    
    # Payment tracking
    payment_status = models.CharField(
        max_length=20,
        choices=BOOKING_PAYMENT_STATUSES,
        default=BOOKING_PAYMENT_PENDING,
        db_index=True,
        help_text='Status of advance payment (pending = awaiting payment)'
    )
    
    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-booking_datetime']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['shop', 'booking_datetime']),
            models.Index(fields=['deal', 'booking_datetime']),
        ]
    
    def __str__(self):
        item_name = self.service.name if self.service else (self.deal.name if self.deal else 'Unknown')
        return f"{self.customer.user.full_name} - {item_name} - {self.booking_datetime}"
    
    @property
    def is_deal_booking(self):
        """Returns True if this is a deal booking, False if service booking."""
        return self.deal is not None
