"""
Django signals for automatically syncing shops/services/staff to Pinecone in real-time.
"""
import logging
import threading
from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Thread-local storage to track shop deletion context
# This prevents individual service deletion signals from queuing redundant tasks
# when a shop is being deleted (the shop deletion handler does a batch delete)
_shop_deletion_context = threading.local()


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
    """Handle shop save - queue async sync to Pinecone if active, remove if inactive."""
    from apps.agent.tasks import sync_single_shop_task, remove_shop_from_pinecone_task, remove_shop_services_from_pinecone_task
    
    # Capture values for the closure (instance may change after transaction)
    shop_id = str(instance.id)
    shop_name = instance.name
    is_active = instance.is_active
    
    if is_active:
        # Shop is active - queue async sync to Pinecone AFTER transaction commits
        def queue_sync():
            logger.info(f"Shop {shop_name} transaction committed, queuing Pinecone sync")
            sync_single_shop_task.delay(shop_id)
        transaction.on_commit(queue_sync)
    else:
        # Shop was deactivated - queue async removal from Pinecone
        service_ids = list(instance.services.values_list('id', flat=True))
        
        def queue_removal():
            logger.info(f"Shop {shop_name} deactivated, queuing Pinecone removal")
            remove_shop_from_pinecone_task.delay(shop_id)
            if service_ids:
                remove_shop_services_from_pinecone_task.delay([str(sid) for sid in service_ids])
        transaction.on_commit(queue_removal)


@receiver(pre_delete, sender='shops.Shop')
def shop_deleted_handler(sender, instance, **kwargs):
    """Handle shop deletion - queue async removal from Pinecone."""
    from apps.agent.tasks import remove_shop_from_pinecone_task, remove_shop_services_from_pinecone_task
    
    logger.info(f"Shop {instance.name} being deleted, queuing Pinecone removal")
    
    # Get service IDs before deletion
    service_ids = list(instance.services.values_list('id', flat=True))
    
    # Mark that we're deleting this shop's services (batch delete handles them)
    # This prevents individual service signals from queuing duplicate tasks
    if not hasattr(_shop_deletion_context, 'service_ids'):
        _shop_deletion_context.service_ids = set()
    _shop_deletion_context.service_ids.update(str(sid) for sid in service_ids)
    
    # Queue async removal
    remove_shop_from_pinecone_task.delay(str(instance.id))
    
    if service_ids:
        remove_shop_services_from_pinecone_task.delay([str(sid) for sid in service_ids])


# ============ SERVICE SIGNALS ============

@receiver(post_save, sender='services.Service')
def service_saved_handler(sender, instance, created, **kwargs):
    """Handle service save - queue async sync to Pinecone if active, remove if inactive."""
    from apps.agent.tasks import sync_single_service_task, remove_service_from_pinecone_task
    
    # Capture values for the closure
    service_id = str(instance.id)
    service_name = instance.name
    is_active = instance.is_active and instance.shop.is_active
    
    if is_active:
        # Service and shop are active - queue async sync AFTER transaction commits
        # Note: We only sync the service here, not the shop - shop sync happens via shop_saved_handler
        # This prevents redundant shop syncs when bulk creating services
        def queue_sync():
            logger.info(f"Service {service_name} transaction committed, queuing Pinecone sync")
            sync_single_service_task.delay(service_id)
        transaction.on_commit(queue_sync)
    else:
        # Service or shop was deactivated - queue async removal from Pinecone
        def queue_removal():
            logger.info(f"Service {service_name} or its shop deactivated, queuing Pinecone removal")
            remove_service_from_pinecone_task.delay(service_id)
        transaction.on_commit(queue_removal)


@receiver(pre_delete, sender='services.Service')
def service_deleted_handler(sender, instance, **kwargs):
    """Handle service deletion - queue async removal from Pinecone."""
    from apps.agent.tasks import remove_service_from_pinecone_task
    
    service_id = str(instance.id)
    service_name = instance.name
    
    # Check if this service is being deleted as part of a shop deletion
    # If so, skip - the batch task from shop_deleted_handler handles it
    if hasattr(_shop_deletion_context, 'service_ids') and service_id in _shop_deletion_context.service_ids:
        logger.debug(f"Service {service_name} skipped (part of shop deletion batch)")
        return
    
    # For individual service deletion, queue the task
    logger.info(f"Service {service_name} being deleted, queuing Pinecone removal")
    remove_service_from_pinecone_task.delay(service_id)


# ============ STAFF SIGNALS ============

@receiver(post_save, sender='staff.StaffMember')
def staff_saved_handler(sender, instance, created, **kwargs):
    """Handle staff save - queue async update of shop in Pinecone to include staff info."""
    from apps.agent.tasks import sync_single_shop_task
    
    # When staff is created or accepts invitation, update the shop's Pinecone entry
    if instance.is_active and instance.shop and instance.shop.is_active and instance.user:
        shop_id = str(instance.shop.id)
        staff_name = instance.name
        
        def queue_sync():
            logger.info(f"Staff {staff_name} accepted/active, queuing shop Pinecone update")
            sync_single_shop_task.delay(shop_id)
        transaction.on_commit(queue_sync)


@receiver(pre_delete, sender='staff.StaffMember')
def staff_deleted_handler(sender, instance, **kwargs):
    """Handle staff deletion - queue async update of shop in Pinecone."""
    from apps.agent.tasks import sync_single_shop_task
    
    if instance.shop and instance.shop.is_active:
        shop_id = str(instance.shop.id)
        staff_name = instance.name
        
        # For pre_delete, queue immediately
        logger.info(f"Staff {staff_name} being deleted, queuing shop Pinecone update")
        sync_single_shop_task.delay(shop_id)
