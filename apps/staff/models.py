"""
Staff models
"""
from django.db import models
from apps.core.models import BaseModel


class StaffMember(BaseModel):
    """
    Staff member model - represents employees working at a shop
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='staff_members'
    )
    
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Profile
    bio = models.TextField(blank=True)
    profile_image_url = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Services this staff member can provide (many-to-many through StaffService)
    services = models.ManyToManyField(
        'services.Service',
        through='StaffService',
        related_name='staff_members'
    )
    
    class Meta:
        db_table = 'staff_members'
        verbose_name = 'Staff Member'
        verbose_name_plural = 'Staff Members'
        ordering = ['name']
        indexes = [
            models.Index(fields=['shop', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.shop.name}"


class StaffService(BaseModel):
    """
    Through model for Staff-Service relationship
    Tracks which services a staff member can provide
    """
    staff_member = models.ForeignKey(
        StaffMember,
        on_delete=models.CASCADE,
        related_name='staff_services'
    )
    
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        related_name='service_staff'
    )
    
    # If true, this staff member is the primary/default for this service
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'staff_services'
        verbose_name = 'Staff Service'
        verbose_name_plural = 'Staff Services'
        unique_together = ['staff_member', 'service']
        indexes = [
            models.Index(fields=['service', 'is_primary']),
        ]
    
    def __str__(self):
        return f"{self.staff_member.name} - {self.service.name}"
