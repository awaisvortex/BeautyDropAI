"""
Django signals for automatically syncing shops/services/staff to Pinecone in real-time.
"""
import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def sync_shop_to_pinecone(shop):
    """Sync a shop to Pinecone knowledge base."""
    try:
        from apps.agent.services.embedding_service import EmbeddingService
        from apps.agent.services.pinecone_service import PineconeService
        from apps.agent.models import KnowledgeDocument
        from django.utils import timezone
        
        embedding_service = EmbeddingService()
        pinecone_service = PineconeService()
        
        # Build content for embedding
        services = shop.services.filter(is_active=True)
        service_names = ", ".join([s.name for s in services[:15]])
        categories = set(s.category for s in services if s.category)
        
        # Get active staff (who have accepted - have a linked user)
        staff_members = shop.staff_members.filter(is_active=True, user__isnull=False)
        staff_names = ", ".join([s.name for s in staff_members[:10]])
        
        content = f"""
{shop.name} is a beauty salon located in {shop.city}, {shop.state or shop.country}.

Description: {shop.description or 'A professional beauty salon.'}

Address: {shop.address}, {shop.city}, {shop.state or ''} {shop.postal_code}

Services offered: {service_names or 'Various beauty services'}

Categories: {', '.join(categories) if categories else 'Beauty services'}

{f'Staff members: {staff_names}' if staff_names else ''}

Contact: Phone: {shop.phone}
{f'Email: {shop.email}' if shop.email else ''}
{f'Website: {shop.website}' if shop.website else ''}

Rating: {shop.average_rating} out of 5 stars from {shop.total_reviews} reviews.

{'This is a verified salon.' if shop.is_verified else ''}
""".strip()
        
        # Generate embedding
        embedding = embedding_service.get_embedding(content)
        
        # Upsert to Pinecone
        success = pinecone_service.upsert_shop(shop, embedding)
        
        if success:
            # Update or create knowledge document
            KnowledgeDocument.objects.update_or_create(
                doc_type='shop',
                shop=shop,
                defaults={
                    'pinecone_id': str(shop.id),
                    'pinecone_namespace': PineconeService.NAMESPACE_SHOPS,
                    'content_text': content,
                    'metadata_json': {'shop_name': shop.name},
                    'last_synced_at': timezone.now(),
                    'needs_resync': False,
                    'sync_error': ''
                }
            )
            logger.info(f"Synced shop {shop.name} to Pinecone")
        else:
            logger.error(f"Failed to sync shop {shop.name} to Pinecone")
            
    except Exception as e:
        logger.error(f"Error syncing shop {shop.id} to Pinecone: {e}")
        # Mark for resync
        try:
            from apps.agent.models import KnowledgeDocument
            KnowledgeDocument.objects.update_or_create(
                doc_type='shop',
                shop=shop,
                defaults={
                    'pinecone_id': str(shop.id),
                    'needs_resync': True,
                    'sync_error': str(e)
                }
            )
        except:
            pass


def sync_service_to_pinecone(service):
    """Sync a service to Pinecone knowledge base."""
    try:
        from apps.agent.services.embedding_service import EmbeddingService
        from apps.agent.services.pinecone_service import PineconeService
        from apps.agent.models import KnowledgeDocument
        from django.utils import timezone
        
        embedding_service = EmbeddingService()
        pinecone_service = PineconeService()
        
        # Build content for embedding
        content = f"""
{service.name} at {service.shop.name}

Category: {service.category or 'General'}

Description: {service.description or f'{service.name} service'}

Price: ${service.price}
Duration: {service.duration_minutes} minutes

Location: {service.shop.city}, {service.shop.state or service.shop.country}
""".strip()
        
        # Generate embedding
        embedding = embedding_service.get_embedding(content)
        
        # Upsert to Pinecone
        success = pinecone_service.upsert_service(service, embedding)
        
        if success:
            KnowledgeDocument.objects.update_or_create(
                doc_type='service',
                service=service,
                defaults={
                    'pinecone_id': str(service.id),
                    'pinecone_namespace': PineconeService.NAMESPACE_SERVICES,
                    'content_text': content,
                    'metadata_json': {'service_name': service.name},
                    'last_synced_at': timezone.now(),
                    'needs_resync': False,
                    'sync_error': ''
                }
            )
            logger.info(f"Synced service {service.name} to Pinecone")
        else:
            logger.error(f"Failed to sync service {service.name} to Pinecone")
            
    except Exception as e:
        logger.error(f"Error syncing service {service.id} to Pinecone: {e}")
        try:
            from apps.agent.models import KnowledgeDocument
            KnowledgeDocument.objects.update_or_create(
                doc_type='service',
                service=service,
                defaults={
                    'pinecone_id': str(service.id),
                    'needs_resync': True,
                    'sync_error': str(e)
                }
            )
        except:
            pass


def remove_shop_from_pinecone(shop_id: str):
    """Remove a shop from Pinecone knowledge base."""
    try:
        from apps.agent.services.pinecone_service import PineconeService
        from apps.agent.models import KnowledgeDocument
        
        pinecone_service = PineconeService()
        
        # Delete from Pinecone
        success = pinecone_service.delete([shop_id], namespace=PineconeService.NAMESPACE_SHOPS)
        
        if success:
            logger.info(f"Removed shop {shop_id} from Pinecone")
        
        # Delete knowledge document
        KnowledgeDocument.objects.filter(
            doc_type='shop',
            pinecone_id=shop_id
        ).delete()
        
    except Exception as e:
        logger.error(f"Error removing shop {shop_id} from Pinecone: {e}")


def remove_service_from_pinecone(service_id: str):
    """Remove a service from Pinecone knowledge base."""
    try:
        from apps.agent.services.pinecone_service import PineconeService
        from apps.agent.models import KnowledgeDocument
        
        pinecone_service = PineconeService()
        
        # Delete from Pinecone
        success = pinecone_service.delete([service_id], namespace=PineconeService.NAMESPACE_SERVICES)
        
        if success:
            logger.info(f"Removed service {service_id} from Pinecone")
        
        # Delete knowledge document
        KnowledgeDocument.objects.filter(
            doc_type='service',
            pinecone_id=service_id
        ).delete()
        
    except Exception as e:
        logger.error(f"Error removing service {service_id} from Pinecone: {e}")


# ============ SHOP SIGNALS ============

@receiver(post_save, sender='shops.Shop')
def shop_saved_handler(sender, instance, created, **kwargs):
    """Handle shop save - sync to Pinecone if active, remove if inactive."""
    if instance.is_active:
        # Shop is active - sync to Pinecone
        logger.info(f"Shop {instance.name} saved (active), syncing to Pinecone")
        sync_shop_to_pinecone(instance)
    else:
        # Shop was deactivated - remove from Pinecone
        logger.info(f"Shop {instance.name} deactivated, removing from Pinecone")
        remove_shop_from_pinecone(str(instance.id))
        
        # Also remove all associated services
        for service in instance.services.all():
            remove_service_from_pinecone(str(service.id))


@receiver(pre_delete, sender='shops.Shop')
def shop_deleted_handler(sender, instance, **kwargs):
    """Handle shop deletion - remove from Pinecone."""
    logger.info(f"Shop {instance.name} being deleted, removing from Pinecone")
    remove_shop_from_pinecone(str(instance.id))
    
    # Also remove all associated services
    for service in instance.services.all():
        remove_service_from_pinecone(str(service.id))


# ============ SERVICE SIGNALS ============

@receiver(post_save, sender='services.Service')
def service_saved_handler(sender, instance, created, **kwargs):
    """Handle service save - sync to Pinecone if active, remove if inactive."""
    if instance.is_active and instance.shop.is_active:
        # Service and shop are active - sync to Pinecone
        logger.info(f"Service {instance.name} saved (active), syncing to Pinecone")
        sync_service_to_pinecone(instance)
        
        # Also update the shop (to include new service in shop content)
        sync_shop_to_pinecone(instance.shop)
    else:
        # Service or shop was deactivated - remove from Pinecone
        logger.info(f"Service {instance.name} or its shop deactivated, removing from Pinecone")
        remove_service_from_pinecone(str(instance.id))


@receiver(pre_delete, sender='services.Service')
def service_deleted_handler(sender, instance, **kwargs):
    """Handle service deletion - remove from Pinecone."""
    logger.info(f"Service {instance.name} being deleted, removing from Pinecone")
    remove_service_from_pinecone(str(instance.id))


# ============ STAFF SIGNALS ============

@receiver(post_save, sender='staff.StaffMember')
def staff_saved_handler(sender, instance, created, **kwargs):
    """Handle staff save - update shop in Pinecone to include staff info."""
    # When staff is created or accepts invitation, update the shop's Pinecone entry
    if instance.is_active and instance.shop and instance.shop.is_active:
        # Check if staff has accepted (has a linked user)
        if instance.user:
            logger.info(f"Staff {instance.name} accepted/active, updating shop in Pinecone")
            sync_shop_to_pinecone(instance.shop)


@receiver(pre_delete, sender='staff.StaffMember')
def staff_deleted_handler(sender, instance, **kwargs):
    """Handle staff deletion - update shop in Pinecone."""
    if instance.shop and instance.shop.is_active:
        logger.info(f"Staff {instance.name} being deleted, updating shop in Pinecone")
        # Re-sync shop to update staff list
        sync_shop_to_pinecone(instance.shop)
