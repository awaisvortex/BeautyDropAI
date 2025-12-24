"""
Management command to sync shop/service data to Pinecone knowledge base.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.shops.models import Shop
from apps.services.models import Service
from apps.agent.models import KnowledgeDocument
from apps.agent.services.embedding_service import EmbeddingService
from apps.agent.services.pinecone_service import PineconeService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync shop and service data to Pinecone knowledge base'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform full sync of all shops and services'
        )
        parser.add_argument(
            '--shop-id',
            type=str,
            help='Sync a specific shop by UUID'
        )
        parser.add_argument(
            '--incremental',
            action='store_true',
            help='Only sync items marked for resync'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting knowledge base sync...')
        
        embedding_service = EmbeddingService()
        pinecone_service = PineconeService()
        
        shops_synced = 0
        services_synced = 0
        errors = 0
        
        # Determine what to sync
        if options['shop_id']:
            shops = Shop.objects.filter(id=options['shop_id'], is_active=True)
        elif options['incremental']:
            # Get shops that need resync
            doc_ids = KnowledgeDocument.objects.filter(
                needs_resync=True, doc_type='shop'
            ).values_list('shop_id', flat=True)
            shops = Shop.objects.filter(id__in=doc_ids, is_active=True)
        else:
            shops = Shop.objects.filter(is_active=True)
        
        total_shops = shops.count()
        self.stdout.write(f'Found {total_shops} shops to sync')
        
        for i, shop in enumerate(shops, 1):
            try:
                # Build content text for embedding
                content = self._build_shop_content(shop)
                
                if options['dry_run']:
                    self.stdout.write(f'[DRY-RUN] Would sync shop: {shop.name}')
                    continue
                
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
                    shops_synced += 1
                    self.stdout.write(f'[{i}/{total_shops}] Synced shop: {shop.name}')
                else:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'[{i}/{total_shops}] Failed to sync shop: {shop.name}')
                    )
                
            except Exception as e:
                errors += 1
                logger.error(f'Error syncing shop {shop.id}: {e}')
                self.stdout.write(
                    self.style.ERROR(f'[{i}/{total_shops}] Error syncing {shop.name}: {e}')
                )
                
                # Record error
                KnowledgeDocument.objects.update_or_create(
                    doc_type='shop',
                    shop=shop,
                    defaults={
                        'pinecone_id': str(shop.id),
                        'pinecone_namespace': PineconeService.NAMESPACE_SHOPS,
                        'content_text': '',
                        'metadata_json': {},
                        'last_synced_at': timezone.now(),
                        'needs_resync': True,
                        'sync_error': str(e)
                    }
                )
        
        # Sync services if full sync
        if options['full'] and not options['dry_run']:
            self.stdout.write('\nSyncing services...')
            services = Service.objects.filter(
                is_active=True,
                shop__is_active=True
            ).select_related('shop')
            
            total_services = services.count()
            self.stdout.write(f'Found {total_services} services to sync')
            
            for i, service in enumerate(services, 1):
                try:
                    content = self._build_service_content(service)
                    embedding = embedding_service.get_embedding(content)
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
                        services_synced += 1
                        
                except Exception as e:
                    errors += 1
                    logger.error(f'Error syncing service {service.id}: {e}')
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Sync completed!'))
        self.stdout.write(f'  Shops synced: {shops_synced}')
        self.stdout.write(f'  Services synced: {services_synced}')
        if errors:
            self.stdout.write(self.style.WARNING(f'  Errors: {errors}'))
    
    def _build_shop_content(self, shop) -> str:
        """Build content text for shop embedding."""
        services = shop.services.filter(is_active=True)
        service_names = ", ".join([s.name for s in services[:15]])
        categories = set(s.category for s in services if s.category)
        
        return f"""
{shop.name} is a beauty salon located in {shop.city}, {shop.state or shop.country}.

Description: {shop.description or 'A professional beauty salon.'}

Address: {shop.address}, {shop.city}, {shop.state or ''} {shop.postal_code}

Services offered: {service_names or 'Various beauty services'}

Categories: {', '.join(categories) if categories else 'Beauty services'}

Contact: Phone: {shop.phone}
{f'Email: {shop.email}' if shop.email else ''}
{f'Website: {shop.website}' if shop.website else ''}

Rating: {shop.average_rating} out of 5 stars from {shop.total_reviews} reviews.

{'This is a verified salon.' if shop.is_verified else ''}
""".strip()
    
    def _build_service_content(self, service) -> str:
        """Build content text for service embedding."""
        return f"""
{service.name} at {service.shop.name}

Category: {service.category or 'General'}

Description: {service.description or f'{service.name} service'}

Price: ${service.price}
Duration: {service.duration_minutes} minutes

Location: {service.shop.city}, {service.shop.state or service.shop.country}
""".strip()
