"""
Client model for salon owners
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.validators import validate_phone_number
from apps.core.utils.constants import SUBSCRIPTION_STATUSES, SUBSCRIPTION_STATUS_TRIAL


class Client(BaseModel):
    """
    Client (Salon Owner) profile
    """
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='client_profile'
    )
    
    business_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, validators=[validate_phone_number])
    business_address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Subscription details
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUSES,
        default=SUBSCRIPTION_STATUS_TRIAL
    )
    subscription_plan = models.CharField(max_length=50, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Limits based on subscription
    max_shops = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'clients'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
    
    def __str__(self):
        return f"{self.business_name} - {self.user.email}"
