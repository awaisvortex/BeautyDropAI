"""
Celery tasks for the AI Agent.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='agent.sync_knowledge_base')
def sync_knowledge_base_task(full_sync=False):
    """
    Celery task to sync knowledge base to Pinecone.
    
    Args:
        full_sync: If True, syncs all items. If False, only syncs items marked for resync.
    
    This task is scheduled to run hourly to catch any missed syncs.
    """
    from django.core.management import call_command
    from io import StringIO
    
    try:
        output = StringIO()
        
        if full_sync:
            logger.info("Running full knowledge base sync...")
            call_command('sync_knowledge_base', '--full', stdout=output)
        else:
            logger.info("Running incremental knowledge base sync...")
            call_command('sync_knowledge_base', '--incremental', stdout=output)
        
        result = output.getvalue()
        logger.info(f"Knowledge base sync completed: {result}")
        
        return {"success": True, "output": result}
        
    except Exception as e:
        logger.error(f"Knowledge base sync failed: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name='agent.cleanup_knowledge_base')
def cleanup_knowledge_base_task():
    """
    Celery task to cleanup deleted/inactive items from Pinecone.
    
    Removes any orphaned or inactive shops/services from the knowledge base.
    """
    from django.core.management import call_command
    from io import StringIO
    
    try:
        output = StringIO()
        logger.info("Running knowledge base cleanup...")
        call_command('sync_knowledge_base', '--cleanup-only', stdout=output)
        
        result = output.getvalue()
        logger.info(f"Knowledge base cleanup completed: {result}")
        
        return {"success": True, "output": result}
        
    except Exception as e:
        logger.error(f"Knowledge base cleanup failed: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name='agent.sync_single_shop')
def sync_single_shop_task(shop_id: str):
    """
    Celery task to sync a single shop to Pinecone.
    
    Args:
        shop_id: UUID of the shop to sync.
    
    This is called when real-time sync fails and needs to be retried.
    """
    try:
        from apps.shops.models import Shop
        from apps.agent.signals import sync_shop_to_pinecone
        
        shop = Shop.objects.get(id=shop_id, is_active=True)
        sync_shop_to_pinecone(shop)
        
        logger.info(f"Successfully synced shop {shop.name}")
        return {"success": True, "shop": shop.name}
        
    except Shop.DoesNotExist:
        logger.warning(f"Shop {shop_id} not found or inactive")
        return {"success": False, "error": "Shop not found or inactive"}
    except Exception as e:
        logger.error(f"Failed to sync shop {shop_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name='agent.sync_single_service')
def sync_single_service_task(service_id: str):
    """
    Celery task to sync a single service to Pinecone.
    
    Args:
        service_id: UUID of the service to sync.
    """
    try:
        from apps.services.models import Service
        from apps.agent.signals import sync_service_to_pinecone
        
        service = Service.objects.get(id=service_id, is_active=True, shop__is_active=True)
        sync_service_to_pinecone(service)
        
        logger.info(f"Successfully synced service {service.name}")
        return {"success": True, "service": service.name}
        
    except Service.DoesNotExist:
        logger.warning(f"Service {service_id} not found or inactive")
        return {"success": False, "error": "Service not found or inactive"}
    except Exception as e:
        logger.error(f"Failed to sync service {service_id}: {e}")
        return {"success": False, "error": str(e)}
