"""
Shop views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count

from apps.core.permissions import IsClient, IsShopOwner
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
        
        # Clients see only their shops
        if self.request.user.is_authenticated and self.request.user.role == 'client':
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
        description="Delete a shop (salon owners only)",
        responses={
            204: OpenApiResponse(description="Shop deleted successfully"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Shops - Client']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
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
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_active', 'dashboard']:
            return [IsClient(), IsShopOwner()]
        elif self.action in ['search', 'public']:
            return [AllowAny()]
        elif self.action == 'my_shops':
            return [IsClient()]
        return super().get_permissions()
