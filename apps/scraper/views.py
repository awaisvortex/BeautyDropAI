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
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.core.serializers import SuccessResponseSerializer

from apps.core.permissions import IsClient
from apps.clients.models import Client

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
        description="""Get details of a specific scrape job including extracted data.
        
Returns HTTP 202 (Accepted) while job is still processing (pending/scraping/parsing/creating).
Returns HTTP 200 (OK) when job is completed or failed.
Frontend should poll this endpoint and show loading until HTTP 200 is returned.""",
        responses={
            200: ScrapeJobSerializer,
            202: OpenApiResponse(description="Job still processing - poll again"),
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
        
        # Return 202 while still processing, 200 when complete/failed
        processing_statuses = [
            ScrapeJobStatus.PENDING,
            ScrapeJobStatus.SCRAPING,
            ScrapeJobStatus.PARSING,
            ScrapeJobStatus.CREATING,
        ]
        
        if scrape_job.status in processing_statuses:
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        
        # Only return 200 for COMPLETED, CONFIRMED, or FAILED
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
            # If shop still exists, block re-confirmation
            if scrape_job.shop:
                return Response(
                    {
                        'error': 'Shop already created from this scrape job',
                        'shop_id': str(scrape_job.shop.id),
                    },
                    status=status.HTTP_409_CONFLICT
                )
            else:
                # Shop was deleted - allow re-confirmation by resetting status
                logger.info(f"Scrape job {pk} was confirmed but shop was deleted, allowing re-confirm")
                scrape_job.status = ScrapeJobStatus.COMPLETED
                scrape_job.save(update_fields=['status', 'updated_at'])
        
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
        deals_data = extracted.get('deals', [])
        
        if not use_extracted:
            shop_data = {}
            services_data = []
            schedule_data = []
            deals_data = []
        
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
        
        # Update status to CREATING
        scrape_job.status = ScrapeJobStatus.CREATING
        scrape_job.save(update_fields=['status', 'updated_at'])
        
        # Queue async task for shop creation
        from .tasks import create_shop_from_scrape_task
        
        create_shop_from_scrape_task.delay(
            scrape_job_id=str(scrape_job.id),
            shop_data=shop_data,
            services_data=services_data,
            schedule_data=schedule_data,
            deals_data=deals_data,
        )
        
        logger.info(f"Queued shop creation task for scrape job {scrape_job.id}")
        
        return Response({
            'success': True,
            'message': 'Shop creation started. This may take a few minutes for shops with many services.',
            'job_id': str(scrape_job.id),
            'status': 'creating',
            'services_count': len(services_data),
            'deals_count': len(deals_data),
        }, status=status.HTTP_202_ACCEPTED)
    
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
