"""
Signals for Customer app.
Auto-creates Customer profile when a User with role 'customer' is created.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.authentication.models import User
from .models import Customer
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    """
    Auto-create Customer profile when a User is created with role 'customer'.
    """
    if created and instance.role == 'customer':
        try:
            Customer.objects.create(user=instance)
            logger.info(f"Created Customer profile for user {instance.email}")
        except Exception as e:
            logger.error(f"Error creating Customer profile for {instance.email}: {e}")


@receiver(post_save, sender=User)
def save_customer_profile(sender, instance, **kwargs):
    """
    Save Customer profile when User is saved.
    """
    if instance.role == 'customer' and hasattr(instance, 'customer_profile'):
        instance.customer_profile.save()
