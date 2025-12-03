"""
Schedule and TimeSlot models
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils.constants import DAYS_OF_WEEK, SLOT_STATUSES, SLOT_STATUS_AVAILABLE


class ShopSchedule(BaseModel):
    """
    Weekly schedule for a shop (Cal.com-like)
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Slot configuration
    slot_duration_minutes = models.IntegerField(default=30)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_schedules'
        verbose_name = 'Shop Schedule'
        verbose_name_plural = 'Shop Schedules'
        unique_together = ['shop', 'day_of_week']
        ordering = ['day_of_week', 'start_time']
    
    def __str__(self):
        return f"{self.shop.name} - {self.day_of_week}"


class TimeSlot(BaseModel):
    """
    Individual time slot for bookings
    """
    schedule = models.ForeignKey(
        ShopSchedule,
        on_delete=models.CASCADE,
        related_name='time_slots'
    )
    
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    
    status = models.CharField(
        max_length=20,
        choices=SLOT_STATUSES,
        default=SLOT_STATUS_AVAILABLE,
        db_index=True
    )
    
    staff_member = models.ForeignKey(
        'staff.StaffMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_slots',
        help_text='Staff member pre-assigned to this time slot'
    )
    
    class Meta:
        db_table = 'time_slots'
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['schedule', 'start_datetime', 'status']),
        ]
    
    def __str__(self):
        return f"{self.start_datetime} - {self.status}"
