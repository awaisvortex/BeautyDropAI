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
