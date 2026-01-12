"""
Shop model
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.validators import validate_phone_number, validate_postal_code


class Shop(BaseModel):
    """
    Salon shop model
    """
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='shops'
    )
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Location
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, validators=[validate_postal_code])
    country = models.CharField(max_length=100, default='USA')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Contact
    phone = models.CharField(max_length=20, validators=[validate_phone_number])
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Media
    logo_url = models.URLField(blank=True)
    cover_image_url = models.TextField(
        blank=True,
        help_text='Cover image URL or base64 encoded image. Accepts any string format until GCP bucket is implemented.'
    )
    
    # Timezone
    timezone = models.CharField(
        max_length=63,
        default='UTC',
        help_text='Shop timezone (IANA timezone, e.g., Asia/Karachi, Europe/London, America/Los_Angeles)'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    # Ratings
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = models.IntegerField(default=0)
    
    # Deal booking capacity (max concurrent deals at same time)
    max_concurrent_deal_bookings = models.PositiveIntegerField(
        default=3,
        help_text='Maximum number of deal bookings that can happen at the same time slot'
    )
    
    # Advance payment settings
    advance_payment_enabled = models.BooleanField(
        default=True,
        help_text='Whether customers must pay advance deposit to confirm booking'
    )
    advance_payment_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text='Percentage of service price required as advance deposit (0-100)'
    )
    
    class Meta:
        db_table = 'shops'
        verbose_name = 'Shop'
        verbose_name_plural = 'Shops'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['client', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.city}"
