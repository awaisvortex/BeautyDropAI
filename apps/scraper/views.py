"""
Scraper API Views

Endpoints:
- POST /api/v1/scraper/submit/ - Submit URL for scraping
- GET /api/v1/scraper/ - List user's scrape jobs
- GET /api/v1/scraper/{id}/ - Get scrape job details
- POST /api/v1/scraper/{id}/confirm/ - Confirm and create shop
- DELETE /api/v1/scraper/{id}/cancel/ - Cancel/delete a job
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.core.serializers import SuccessResponseSerializer

from apps.core.permissions import IsClient
from apps.clients.models import Client
from apps.shops.models import Shop
from apps.services.models import Service
from apps.schedules.models import ShopSchedule

from .models import ScrapeJob, ScrapeJobStatus
from .serializers import (
    ScrapeSubmitSerializer,
    ScrapeJobSerializer,
    ScrapeJobListSerializer,
    ScrapeConfirmSerializer,
    ScrapeConfirmResponseSerializer,
)
from .tasks import scrape_website_task

logger = logging.getLogger(__name__)


class ScraperViewSet(viewsets.GenericViewSet):
    """
    ViewSet for website scraping operations.
    
    Allows clients to submit URLs for scraping and create shops from extracted data.
    """
    permission_classes = [IsAuthenticated, IsClient]
    
    def get_queryset(self):
        """Filter to current user's scrape jobs"""
        user = self.request.user
        try:
            client = Client.objects.get(user=user)
            return ScrapeJob.objects.filter(client=client).select_related('shop')
        except Client.DoesNotExist:
            return ScrapeJob.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'submit':
            return ScrapeSubmitSerializer
        elif self.action == 'confirm':
            return ScrapeConfirmSerializer
        elif self.action == 'list':
            return ScrapeJobListSerializer
        return ScrapeJobSerializer
    
    @extend_schema(
        summary="Submit URL for scraping",
        description="Submit a salon website URL to scrape. Creates a ScrapeJob and queues async scraping task.",
        request=ScrapeSubmitSerializer,
        responses={
            201: ScrapeJobSerializer,
            400: OpenApiResponse(description="Invalid URL or client not found"),
            409: OpenApiResponse(description="Scraping job already in progress for this URL"),
        },
        tags=['Scraper']
    )
    @action(detail=False, methods=['post'])
    def submit(self, request):
        """
        Submit a URL for scraping.
        
        Creates a ScrapeJob and queues async scraping task.
        """
        serializer = ScrapeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        url = serializer.validated_data['url']
        
        # Get client
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            return Response(
                {'error': 'Client profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicate pending/scraping jobs
        existing_job = ScrapeJob.objects.filter(
            client=client,
            url=url,
            status__in=[ScrapeJobStatus.PENDING, ScrapeJobStatus.SCRAPING, ScrapeJobStatus.PARSING]
        ).first()
        
        if existing_job:
            return Response(
                {
                    'error': 'A scraping job for this URL is already in progress',
                    'job_id': str(existing_job.id),
                    'status': existing_job.status,
                },
                status=status.HTTP_409_CONFLICT
            )
        
        # Create scrape job
        scrape_job = ScrapeJob.objects.create(
            client=client,
            url=url,
            status=ScrapeJobStatus.PENDING
        )
        
        # Queue async task
        scrape_website_task.delay(str(scrape_job.id))
        
        logger.info(f"Created scrape job {scrape_job.id} for URL: {url}")
        
        return Response(
            ScrapeJobSerializer(scrape_job).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="List scrape jobs",
        description="List all scrape jobs for the current user.",
        responses={200: ScrapeJobListSerializer(many=True)},
        tags=['Scraper']
    )
    def list(self, request):
        """List all scrape jobs for the current user."""
        queryset = self.get_queryset().order_by('-created_at')
        serializer = ScrapeJobListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get scrape job details",
        description="Get details of a specific scrape job including extracted data.",
        responses={
            200: ScrapeJobSerializer,
            404: OpenApiResponse(description="Scrape job not found"),
        },
        tags=['Scraper']
    )
    def retrieve(self, request, pk=None):
        """Get details of a specific scrape job."""
        try:
            scrape_job = self.get_queryset().get(pk=pk)
        except ScrapeJob.DoesNotExist:
            return Response(
                {'error': 'Scrape job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ScrapeJobSerializer(scrape_job)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Confirm and create shop",
        description="Confirm scrape job and create shop with extracted data. Optionally allows overriding extracted data.",
        request=ScrapeConfirmSerializer,
        responses={
            200: ScrapeConfirmResponseSerializer,
            400: OpenApiResponse(description="Invalid status or missing data"),
            404: OpenApiResponse(description="Scrape job not found"),
            409: OpenApiResponse(description="Shop already created"),
        },
        tags=['Scraper']
    )
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm scrape job and create shop with extracted data."""
        try:
            scrape_job = self.get_queryset().get(pk=pk)
        except ScrapeJob.DoesNotExist:
            return Response(
                {'error': 'Scrape job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check status
        if scrape_job.status == ScrapeJobStatus.CONFIRMED:
            return Response(
                {
                    'error': 'Shop already created from this scrape job',
                    'shop_id': str(scrape_job.shop.id) if scrape_job.shop else None,
                },
                status=status.HTTP_409_CONFLICT
            )
        
        if scrape_job.status != ScrapeJobStatus.COMPLETED:
            return Response(
                {
                    'error': f'Cannot confirm job with status: {scrape_job.status}',
                    'current_status': scrape_job.status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not scrape_job.extracted_data:
            return Response(
                {'error': 'No extracted data available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse request
        serializer = ScrapeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        use_extracted = serializer.validated_data.get('use_extracted', True)
        extracted = scrape_job.extracted_data
        
        # Merge extracted data with overrides
        shop_data = extracted.get('shop', {})
        services_data = extracted.get('services', [])
        schedule_data = extracted.get('schedule', [])
        
        if not use_extracted:
            shop_data = {}
            services_data = []
            schedule_data = []
        
        # Apply overrides
        if serializer.validated_data.get('shop'):
            shop_data.update(serializer.validated_data['shop'])
        if serializer.validated_data.get('services'):
            services_data = serializer.validated_data['services']
        if serializer.validated_data.get('schedule'):
            schedule_data = serializer.validated_data['schedule']
        
        # Validate required shop data
        if not shop_data.get('name'):
            return Response(
                {'error': 'Shop name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Clean and prepare phone number (remove non-digits except +)
        phone = shop_data.get('phone', '')
        if phone:
            # Keep only digits and leading +
            cleaned_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            if not cleaned_phone.startswith('+'):
                cleaned_phone = '+1' + cleaned_phone  # Default to US
            phone = cleaned_phone[:15]  # Max 15 chars
        else:
            phone = '+10000000000'  # Default placeholder
        
        # Ensure required fields have defaults
        address = shop_data.get('address', '') or 'Address TBD'
        city = shop_data.get('city', '') or 'City TBD'
        postal_code = shop_data.get('postal_code', '') or '00000'
        
        try:
            with transaction.atomic():
                # Create shop
                shop = Shop.objects.create(
                    client=scrape_job.client,
                    name=shop_data.get('name', ''),
                    description=shop_data.get('description', ''),
                    address=address,
                    city=city,
                    state=shop_data.get('state', ''),
                    postal_code=postal_code,
                    country=shop_data.get('country', 'USA'),
                    phone=phone,
                    email=shop_data.get('email', ''),
                    website=shop_data.get('website', scrape_job.url),
                    timezone=shop_data.get('timezone', 'UTC'),
                    is_active=True,
                )
                
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
                
                # Create schedules
                schedules_created = 0
                for sched in schedule_data:
                    day = sched.get('day_of_week')
                    if not day:
                        continue
                    
                    is_closed = sched.get('is_closed', False)
                    start_time = sched.get('start_time')
                    end_time = sched.get('end_time')
                    
                    # Skip closed days or missing times
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
                
                # Update scrape job
                scrape_job.status = ScrapeJobStatus.CONFIRMED
                scrape_job.shop = shop
                scrape_job.save(update_fields=['status', 'shop', 'updated_at'])
                
                logger.info(f"Created shop {shop.id} from scrape job {scrape_job.id}")
                
                return Response({
                    'success': True,
                    'shop_id': str(shop.id),
                    'shop_name': shop.name,
                    'services_created': services_created,
                    'schedules_created': schedules_created,
                })
                
        except Exception as e:
            logger.error(f"Failed to create shop from scrape job {scrape_job.id}: {e}")
            return Response(
                {'error': f'Failed to create shop: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Cancel/delete scrape job",
        description="Cancel and delete a pending or failed scrape job.",
        responses={
            200: SuccessResponseSerializer,
            400: OpenApiResponse(description="Cannot delete confirmed jobs"),
            404: OpenApiResponse(description="Scrape job not found"),
        },
        tags=['Scraper']
    )
    @action(detail=True, methods=['delete'])
    def cancel(self, request, pk=None):
        """Cancel/delete a scrape job."""
        try:
            scrape_job = self.get_queryset().get(pk=pk)
        except ScrapeJob.DoesNotExist:
            return Response(
                {'error': 'Scrape job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if scrape_job.status in [ScrapeJobStatus.CONFIRMED]:
            return Response(
                {'error': 'Cannot delete confirmed scrape jobs'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        job_id = str(scrape_job.id)
        scrape_job.delete()
        
        return Response({
            'success': True,
            'deleted_job_id': job_id,
        })
