"""
Service model
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.validators import validate_positive_decimal, validate_duration


class Service(BaseModel):
    """
    Service offered by a shop
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='services'
    )
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_positive_decimal]
    )
    
    # Duration
    duration_minutes = models.IntegerField(validators=[validate_duration])
    
    # Buffer time before next booking can be made (in minutes)
    # Set to 0 for no buffer, or a positive value for minimum lead time
    buffer_minutes = models.IntegerField(
        default=0,
        help_text='Minimum time buffer between now and earliest bookable slot (0 = no buffer)'
    )
    
    # Category
    category = models.CharField(max_length=100, blank=True)
    
    # Media
    image_url = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Popularity
    booking_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'services'
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['-booking_count', 'name']
        indexes = [
            models.Index(fields=['shop', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.shop.name}"
