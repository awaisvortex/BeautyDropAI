"""
Celery tasks for async scraping operations
"""
import logging
from celery import shared_task
from django.db import transaction

from .models import ScrapeJob, ScrapeJobStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_website_task(self, scrape_job_id: str):
    """
    Async task to scrape a website and extract shop data.
    
    Flow:
    1. Update status to 'scraping'
    2. Fetch and parse website content
    3. Update status to 'parsing'
    4. Use AI to extract structured data
    5. Update status to 'completed' with extracted data
    
    Args:
        scrape_job_id: UUID of the ScrapeJob
    """
    try:
        scrape_job = ScrapeJob.objects.get(id=scrape_job_id)
    except ScrapeJob.DoesNotExist:
        logger.error(f"ScrapeJob {scrape_job_id} not found")
        return
    
    try:
        # Step 1: Update status to scraping
        scrape_job.status = ScrapeJobStatus.SCRAPING
        scrape_job.save(update_fields=['status', 'updated_at'])
        logger.info(f"Starting scrape for job {scrape_job_id}: {scrape_job.url}")
        
        # Step 2: Scrape the website
        from .scraper_service import scrape_website_sync, ScraperError
        
        try:
            platform, scraped_data = scrape_website_sync(scrape_job.url)
        except ScraperError as e:
            raise Exception(f"Scraping failed: {str(e)}")
        
        # Update platform and store raw content
        scrape_job.platform = platform
        scrape_job.raw_content = scraped_data.get('text_content', '')[:50000]  # Limit storage
        scrape_job.status = ScrapeJobStatus.PARSING
        scrape_job.save(update_fields=['platform', 'raw_content', 'status', 'updated_at'])
        logger.info(f"Scraping complete for job {scrape_job_id}, platform: {platform}")
        
        # Step 3: Parse with AI
        from .ai_parser import parse_with_ai
        
        extracted_data = parse_with_ai(scraped_data)
        
        # Step 4: Save results
        scrape_job.extracted_data = extracted_data
        scrape_job.status = ScrapeJobStatus.COMPLETED
        scrape_job.save(update_fields=['extracted_data', 'status', 'updated_at'])
        
        logger.info(f"AI parsing complete for job {scrape_job_id}")
        logger.info(f"Extracted: shop={extracted_data.get('shop', {}).get('name')}, "
                   f"services={len(extracted_data.get('services', []))}, "
                   f"schedule={len(extracted_data.get('schedule', []))}")
        
        return {
            'status': 'completed',
            'job_id': str(scrape_job_id),
            'shop_name': extracted_data.get('shop', {}).get('name'),
            'services_count': len(extracted_data.get('services', [])),
        }
        
    except Exception as e:
        logger.error(f"Scrape task failed for job {scrape_job_id}: {str(e)}")
        
        # Update job with error
        scrape_job.status = ScrapeJobStatus.FAILED
        scrape_job.error_message = str(e)[:1000]
        scrape_job.save(update_fields=['status', 'error_message', 'updated_at'])
        
        # Retry for transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        return {
            'status': 'failed',
            'job_id': str(scrape_job_id),
            'error': str(e),
        }


@shared_task
def cleanup_old_scrape_jobs():
    """
    Periodic task to clean up old scrape jobs.
    Runs daily to remove jobs older than 30 days.
    """
    from datetime import timedelta
    from django.utils import timezone
    
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_count, _ = ScrapeJob.objects.filter(
        created_at__lt=cutoff_date
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old scrape jobs")
    return {'deleted_count': deleted_count}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def create_shop_from_scrape_task(
    self, 
    scrape_job_id: str, 
    shop_data: dict, 
    services_data: list, 
    schedule_data: list,
    deals_data: list = None  # Optional list of deal dicts
):
    """
    Async task to create shop, services, deals, and schedules from confirmed scrape job.
    
    This runs in the background so the user doesn't have to wait for
    potentially hundreds of services to be created.
    
    Args:
        scrape_job_id: UUID of the ScrapeJob
        shop_data: Shop details dict
        services_data: List of service dicts
        schedule_data: List of schedule dicts
        deals_data: Optional list of deal dicts
    """
    from apps.shops.models import Shop
    from apps.services.models import Service, Deal
    from apps.schedules.models import ShopSchedule
    
    # Default to empty list if not provided
    if deals_data is None:
        deals_data = []
    
    try:
        scrape_job = ScrapeJob.objects.get(id=scrape_job_id)
    except ScrapeJob.DoesNotExist:
        logger.error(f"ScrapeJob {scrape_job_id} not found for shop creation")
        return {'status': 'error', 'message': 'Job not found'}
    
    logger.info(f"Creating shop from scrape job {scrape_job_id} with {len(services_data)} services")
    
    try:
        with transaction.atomic():
            # Clean phone number
            phone = shop_data.get('phone', '')
            if phone:
                cleaned_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
                if not cleaned_phone.startswith('+'):
                    cleaned_phone = '+92' + cleaned_phone  # Default to Pakistan
                phone = cleaned_phone[:15]
            else:
                phone = '+920000000000'
            
            # Ensure required fields have defaults
            address = shop_data.get('address', '') or 'Address TBD'
            city = shop_data.get('city', '') or 'City TBD'
            postal_code = shop_data.get('postal_code', '') or '00000'
            
            # Create shop
            shop = Shop.objects.create(
                client=scrape_job.client,
                name=shop_data.get('name', ''),
                description=shop_data.get('description', ''),
                address=address,
                city=city,
                state=shop_data.get('state', ''),
                postal_code=postal_code,
                country=shop_data.get('country', 'Pakistan'),
                phone=phone,
                email=shop_data.get('email', ''),
                website=shop_data.get('website', scrape_job.url),
                timezone=shop_data.get('timezone', 'Asia/Karachi'),
                is_active=True,
            )
            
            logger.info(f"Created shop {shop.id}: {shop.name}")
            
            # Create services
            services_created = 0
            for svc in services_data:
                if svc.get('name') and svc.get('price') is not None:
                    Service.objects.create(
                        shop=shop,
                        name=svc['name'],
                        description=svc.get('description', ''),
                        price=svc['price'],
                        duration_minutes=svc.get('duration_minutes', 30),
                        category=svc.get('category', ''),
                        is_active=True,
                    )
                    services_created += 1
            
            logger.info(f"Created {services_created} services for shop {shop.id}")
            
            # Create deals
            deals_created = 0
            for deal in deals_data:
                if deal.get('name') and deal.get('included_items'):
                    Deal.objects.create(
                        shop=shop,
                        name=deal['name'],
                        description=deal.get('description', ''),
                        price=deal.get('price', 0),
                        included_items=deal.get('included_items', []),
                        is_active=True,
                    )
                    deals_created += 1
            
            if deals_created > 0:
                logger.info(f"Created {deals_created} deals for shop {shop.id}")
            
            # Create schedules
            schedules_created = 0
            for sched in schedule_data:
                day = sched.get('day_of_week')
                if not day:
                    continue
                
                is_closed = sched.get('is_closed', False)
                start_time = sched.get('start_time')
                end_time = sched.get('end_time')
                
                if is_closed or not start_time or not end_time:
                    continue
                
                ShopSchedule.objects.create(
                    shop=shop,
                    day_of_week=day,
                    start_time=start_time,
                    end_time=end_time,
                    is_active=True,
                )
                schedules_created += 1
            
            logger.info(f"Created {schedules_created} schedules for shop {shop.id}")
            
            # Update scrape job
            scrape_job.status = ScrapeJobStatus.CONFIRMED
            scrape_job.shop = shop
            scrape_job.save(update_fields=['status', 'shop', 'updated_at'])
            
            logger.info(f"Shop creation complete for scrape job {scrape_job_id}")
            
            return {
                'status': 'success',
                'shop_id': str(shop.id),
                'shop_name': shop.name,
                'services_created': services_created,
                'deals_created': deals_created,
                'schedules_created': schedules_created,
            }
            
    except Exception as e:
        logger.error(f"Failed to create shop from scrape job {scrape_job_id}: {e}")
        
        # Update job with error
        scrape_job.status = ScrapeJobStatus.FAILED
        scrape_job.error_message = f"Shop creation failed: {str(e)[:500]}"
        scrape_job.save(update_fields=['status', 'error_message', 'updated_at'])
        
        # Retry for transient errors
        if self.request.retries < self.max_retries:
            # Reset status for retry
            scrape_job.status = ScrapeJobStatus.CREATING
            scrape_job.save(update_fields=['status', 'updated_at'])
            raise self.retry(exc=e)
        
        return {
            'status': 'failed',
            'job_id': str(scrape_job_id),
            'error': str(e),
        }
