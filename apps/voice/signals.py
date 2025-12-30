"""
Django signals for voice agent auto-creation.
Creates ShopVoiceAgent when a Shop is created.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='shops.Shop')
def create_shop_voice_agent(sender, instance, created, **kwargs):
    """
    Auto-create ShopVoiceAgent when a Shop is created.
    This ensures every shop has a voice agent configuration.
    """
    if created:
        from .models import ShopVoiceAgent
        
        try:
            ShopVoiceAgent.objects.create(shop=instance)
            logger.info(f"Created ShopVoiceAgent for new shop: {instance.name}")
        except Exception as e:
            logger.error(f"Failed to create ShopVoiceAgent for {instance.name}: {e}")
