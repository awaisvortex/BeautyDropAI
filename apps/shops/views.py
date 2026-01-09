"""
Shop views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count

from apps.core.permissions import IsClient, IsShopOwner
from apps.core.serializers import SuccessResponseSerializer
from .models import Shop
from .serializers import (
    ShopSerializer,
    ShopDetailSerializer,
    ShopCreateUpdateSerializer,
    ShopSearchSerializer
)


class ShopViewSet(viewsets.ModelViewSet):
    """ViewSet for managing shops"""
    queryset = Shop.objects.select_related('client__user').prefetch_related('services')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'state', 'is_active']
    search_fields = ['name', 'description', 'city', 'address']
    ordering_fields = ['name', 'city', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ShopDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ShopCreateUpdateSerializer
        return ShopSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Handle unauthenticated users (public access)
        if not self.request.user.is_authenticated:
            # Show only active shops to public
            queryset = queryset.filter(is_active=True)
        # Clients see only their shops
        elif self.request.user.is_authenticated and self.request.user.role == 'client':
            if self.action not in ['search', 'public']:
                queryset = queryset.filter(client__user=self.request.user)
        # Customers see only active shops
        elif self.request.user.is_authenticated and self.request.user.role == 'customer':
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @extend_schema(
        summary="List shops",
        description="Get all shops. Salon owners see their shops, customers see active shops.",
        parameters=[
            OpenApiParameter('city', str, description='Filter by city'),
            OpenApiParameter('state', str, description='Filter by state'),
            OpenApiParameter('is_active', bool, description='Filter by active status'),
            OpenApiParameter('search', str, description='Search in name, description, city, address'),
        ],
        responses={200: ShopSerializer(many=True)},
        tags=['Shops - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get shop details",
        description="Retrieve detailed information about a specific shop including services",
        examples=[
            OpenApiExample(
                'Shop Response Example',
                value={
                    'id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'client': '5f8d7f6e-4d3c-2b1a-0e9f-8g7h6i5j4k3l',
                    'client_name': 'Sidra\'s Business',
                    'name': 'Sidra\'s Beauty Salon',
                    'description': 'Premium beauty services',
                    'address': '123 Main Street',
                    'city': 'Karachi',
                    'state': 'Sindh',
                    'postal_code': '75500',
                    'country': 'Pakistan',
                    'phone': '+92-300-1234567',
                    'email': 'info@sidrasbeauty.com',
                    'website': 'https://sidrasbeauty.com',
                    'logo_url': '',
                    'cover_image_url': '',
                    'timezone': 'Asia/Karachi',
                    'is_active': True,
                    'services_count': 5,
                    'created_at': '2025-12-01T10:00:00Z',
                    'updated_at': '2025-12-08T08:00:00Z'
                },
                response_only=True
            )
        ],
        responses={
            200: ShopDetailSerializer,
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create shop",
        description="Create a new shop (salon owners only)",
        request=ShopCreateUpdateSerializer,
        examples=[
            OpenApiExample(
                'Create Shop Example',
                value={
                    'name': 'Sidra\'s Beauty Salon',
                    'description': 'Premium beauty services',
                    'address': '123 Main Street',
                    'city': 'Karachi',
                    'state': 'Sindh',
                    'postal_code': '75500',
                    'country': 'Pakistan',
                    'phone': '+92-300-1234567',
                    'email': 'info@sidrasbeauty.com',
                    'timezone': 'Asia/Karachi',
                    'is_active': True
                },
                request_only=True
            )
        ],
        responses={
            201: ShopSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden - Only salon owners can create shops")
        },
        tags=['Shops - Client']
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != 'client':
            return Response(
                {'error': 'Only salon owners can create shops'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get or create client profile
        from apps.clients.models import Client
        client, created = Client.objects.get_or_create(user=request.user)
        
        shop = serializer.save(client=client)
        return Response(
            ShopSerializer(shop).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Update shop",
        description="Update shop details (salon owners only)",
        request=ShopCreateUpdateSerializer,
        responses={
            200: ShopSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update shop",
        description="Partially update shop details (salon owners only)",
        request=ShopCreateUpdateSerializer,
        responses={
            200: ShopSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete shop",
        description="""
        Delete a shop and ALL associated data (salon owners only).
        
        **This is a permanent action that:**
        - Deletes ALL staff members from the shop
        - Deletes staff user accounts from Clerk (they won't be able to log in anymore)
        - Deletes all services and deals from Pinecone
        - Deletes the shop from Pinecone
        - Deletes the shop and all related data from the database
        
        **Note:** Bookings are preserved for records but will show the shop/staff as deleted.
        """,
        responses={
            200: OpenApiResponse(
                description="Shop deleted successfully",
                response={
                    'type': 'object',
                    'properties': {
                        'success': {'type': 'boolean'},
                        'message': {'type': 'string'},
                        'deleted_shop': {'type': 'string'},
                        'deleted_staff_count': {'type': 'integer'},
                        'deleted_clerk_users': {'type': 'integer'},
                        'deleted_services_count': {'type': 'integer'},
                        'deleted_deals_count': {'type': 'integer'},
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Client']
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        shop_name = instance.name
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Get counts before deletion
        staff_members = list(instance.staff_members.select_related('user').all())
        services_count = instance.services.count()
        deals_count = instance.deals.count()
        
        # Delete all staff members and their Clerk accounts
        from apps.authentication.services.clerk_api import clerk_client
        deleted_staff_count = 0
        deleted_clerk_users = 0
        
        for staff in staff_members:
            staff_name = staff.name
            user = staff.user
            clerk_user_id = user.clerk_user_id if user else None
            
            # Delete staff member
            staff.delete()
            deleted_staff_count += 1
            logger.info(f"Deleted staff member: {staff_name}")
            
            # Delete user from Django DB
            if user:
                try:
                    user.delete()
                    logger.info(f"Deleted user {clerk_user_id} from database")
                except Exception as e:
                    logger.error(f"Failed to delete user {clerk_user_id}: {e}")
            
            # Delete from Clerk
            if clerk_user_id and not clerk_user_id.startswith('local_'):
                if clerk_client.delete_user(clerk_user_id):
                    deleted_clerk_users += 1
        
        # Delete the shop (services, deals, schedules cascade via Django)
        # Pinecone cleanup is handled by pre_delete signal in apps/agent/signals.py
        self.perform_destroy(instance)
        
        return Response({
            "success": True,
            "message": f"Shop '{shop_name}' and all associated data deleted successfully",
            "deleted_shop": shop_name,
            "deleted_staff_count": deleted_staff_count,
            "deleted_clerk_users": deleted_clerk_users,
            "deleted_services_count": services_count,
            "deleted_deals_count": deals_count,
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="My shops",
        description="Get all shops owned by the current salon owner",
        responses={200: ShopSerializer(many=True)},
        tags=['Shops - Client']
    )
    @action(detail=False, methods=['get'], permission_classes=[IsClient])
    def my_shops(self, request):
        """Get current user's shops"""
        shops = self.get_queryset()
        serializer = ShopSerializer(shops, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Toggle shop active status",
        description="Activate or deactivate a shop (salon owners only)",
        request=None,
        responses={
            200: ShopSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Client']
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsClient, IsShopOwner])
    def toggle_active(self, request, pk=None):
        """Toggle shop active status"""
        shop = self.get_object()
        shop.is_active = not shop.is_active
        shop.save(update_fields=['is_active'])
        return Response(ShopSerializer(shop).data)
    
    @extend_schema(
        summary="Search shops",
        description="Search for shops with advanced filters (public endpoint)",
        parameters=[
            OpenApiParameter('query', str, description='Search query'),
            OpenApiParameter('city', str, description='Filter by city'),
            OpenApiParameter('service', str, description='Filter by service name'),
            OpenApiParameter('min_price', float, description='Minimum service price'),
            OpenApiParameter('max_price', float, description='Maximum service price'),
        ],
        responses={200: ShopSerializer(many=True)},
        tags=['Shops - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def search(self, request):
        """Advanced shop search"""
        queryset = Shop.objects.filter(is_active=True)
        
        # Search query
        query = request.query_params.get('query')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(city__icontains=query)
            )
        
        # City filter
        city = request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__iexact=city)
        
        # Service filter
        service = request.query_params.get('service')
        if service:
            queryset = queryset.filter(services__name__icontains=service)
        
        # Price range filter
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(services__price__gte=min_price)
        if max_price:
            queryset = queryset.filter(services__price__lte=max_price)
        
        queryset = queryset.distinct()
        serializer = ShopSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Public shop details",
        description="Get public shop information (no authentication required)",
        responses={
            200: ShopDetailSerializer,
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Public']
    )
    @action(detail=True, methods=['get'], permission_classes=[AllowAny], url_path='public')
    def public(self, request, pk=None):
        """Get public shop details"""
        shop = self.get_object()
        if not shop.is_active:
            return Response(
                {'error': 'Shop is not active'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ShopDetailSerializer(shop)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Shop dashboard",
        description="Get shop statistics and dashboard data (salon owners only)",
        responses={200: dict},
        tags=['Shops - Client']
    )
    @action(detail=True, methods=['get'], permission_classes=[IsClient, IsShopOwner])
    def dashboard(self, request, pk=None):
        """Get shop dashboard statistics"""
        shop = self.get_object()
        from apps.bookings.models import Booking
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        bookings = Booking.objects.filter(shop=shop)
        
        stats = {
            'total_services': shop.services.filter(is_active=True).count(),
            'total_bookings': bookings.count(),
            'bookings_today': bookings.filter(booking_datetime__date=today).count(),
            'bookings_this_week': bookings.filter(booking_datetime__date__gte=week_ago).count(),
            'bookings_this_month': bookings.filter(booking_datetime__date__gte=month_ago).count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'confirmed_bookings': bookings.filter(status='confirmed').count(),
            'total_revenue': sum(b.total_price for b in bookings.filter(status='completed')),
            'revenue_this_month': sum(
                b.total_price for b in bookings.filter(
                    status='completed',
                    booking_datetime__date__gte=month_ago
                )
            ),
        }
        
        return Response(stats)
    
    @extend_schema(
        summary="Get timezone choices",
        description="Get list of all available IANA timezones for dropdown selection (public endpoint)",
        responses={200: dict},
        tags=['Shops - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def timezone_choices(self, request):
        """Get list of all available timezones"""
        import pytz
        
        # Get all timezones and group by region
        all_timezones = pytz.all_timezones
        
        # Group timezones by region
        grouped = {}
        for tz in all_timezones:
            if '/' in tz:
                region = tz.split('/')[0]
                if region not in grouped:
                    grouped[region] = []
                grouped[region].append(tz)
        
        # Also provide a list of common timezones
        common_timezones = [
            'UTC',
            'Asia/Karachi',
            'Asia/Dubai',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Singapore',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'America/New_York',
            'America/Chicago',
            'America/Los_Angeles',
            'America/Toronto',
            'Australia/Sydney',
        ]
        
        return Response({
            'all_timezones': all_timezones,
            'grouped_timezones': grouped,
            'common_timezones': common_timezones
        })
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'search', 'public', 'timezone_choices']:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_active', 'dashboard']:
            return [IsClient(), IsShopOwner()]
        elif self.action == 'my_shops':
            return [IsClient()]
        return super().get_permissions()
