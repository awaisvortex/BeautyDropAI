"""
ScrapeJob model - tracks website scraping jobs for shop creation
"""
from django.db import models
from apps.core.models import BaseModel


class ScrapeJobStatus(models.TextChoices):
    """Status choices for scrape jobs"""
    PENDING = 'pending', 'Pending'
    SCRAPING = 'scraping', 'Scraping'
    PARSING = 'parsing', 'Parsing with AI'
    COMPLETED = 'completed', 'Completed'
    CREATING = 'creating', 'Creating Shop'
    CONFIRMED = 'confirmed', 'Shop Created'
    FAILED = 'failed', 'Failed'


class ScrapeJob(BaseModel):
    """
    Tracks scraping job status for creating shops from URLs.
    
    Flow:
    1. Owner submits URL -> status = pending
    2. Celery starts scraping -> status = scraping
    3. AI parses content -> status = parsing
    4. Extraction complete -> status = completed
    5. Owner confirms -> status = confirmed, shop created
    """
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='scrape_jobs',
        help_text='Client who initiated the scrape'
    )
    
    url = models.URLField(
        max_length=2000,
        help_text='Source URL to scrape'
    )
    
    platform = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Detected platform (google, yelp, booksy, etc.) or empty for generic'
    )
    
    status = models.CharField(
        max_length=20,
        choices=ScrapeJobStatus.choices,
        default=ScrapeJobStatus.PENDING,
        db_index=True
    )
    
    # Scraped content
    raw_content = models.TextField(
        blank=True,
        default='',
        help_text='Raw HTML/text content scraped from the URL'
    )
    
    # AI-extracted data as JSON
    extracted_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Structured data extracted by AI'
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        default='',
        help_text='Error message if scraping failed'
    )
    
    # Reference to created shop
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scrape_jobs',
        help_text='Shop created from this scrape job'
    )
    
    class Meta:
        db_table = 'scrape_jobs'
        verbose_name = 'Scrape Job'
        verbose_name_plural = 'Scrape Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"ScrapeJob {self.id} - {self.url[:50]}... ({self.status})"
