"""
Customer model
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.validators import validate_phone_number
from apps.core.utils.constants import SUBSCRIPTION_STATUSES, SUBSCRIPTION_STATUS_TRIAL


class Customer(BaseModel):
    """
    Customer profile
    """
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    
    phone = models.CharField(max_length=20, validators=[validate_phone_number], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Subscription details
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUSES,
        default=SUBSCRIPTION_STATUS_TRIAL
    )
    subscription_plan = models.CharField(max_length=50, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Preferences
    favorite_shops = models.ManyToManyField(
        'shops.Shop',
        related_name='favorited_by',
        blank=True
    )
    
    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"{self.user.full_name} - {self.user.email}"
