"""
Service views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.permissions import IsClient, IsShopOwner
from .models import Service
from .serializers import ServiceSerializer, ServiceCreateUpdateSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing services"""
    queryset = Service.objects.select_related('shop', 'shop__client__user')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'duration_minutes', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ServiceCreateUpdateSerializer
        return ServiceSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Handle unauthenticated users (public access)
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_active=True)
        # Only show active services to customers
        elif self.request.user.role == 'customer':
            queryset = queryset.filter(is_active=True)
        # Clients see only their services
        elif self.request.user.role == 'client':
            queryset = queryset.filter(shop__client__user=self.request.user)
        
        return queryset
    
    @extend_schema(
        summary="List services",
        description="Get all services. Customers see only active services. Salon owners see only their services.",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
            OpenApiParameter('is_active', bool, description='Filter by active status'),
            OpenApiParameter('search', str, description='Search in name and description'),
        ],
        responses={200: ServiceSerializer(many=True)},
        tags=['Services - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get service details",
        description="Retrieve detailed information about a specific service",
        responses={
            200: ServiceSerializer,
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Services - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create service",
        description="Create a new service (salon owners only). Requires shop_id in request data.",
        request=ServiceCreateUpdateSerializer,
        responses={
            201: ServiceSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden - Only salon owners can create services"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Services - Client']
    )
    def create(self, request, *args, **kwargs):
        # Ensure user is a client
        if request.user.role != 'client':
            return Response(
                {'error': 'Only salon owners can create services'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get shop from request data
        shop_id = request.data.get('shop_id')
        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify shop ownership
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, client__user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found or you do not own this shop'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        service = serializer.save(shop=shop)
        return Response(
            ServiceSerializer(service).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Update service",
        description="Update service details (salon owners only)",
        request=ServiceCreateUpdateSerializer,
        responses={
            200: ServiceSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Services - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update service",
        description="Partially update service details (salon owners only)",
        request=ServiceCreateUpdateSerializer,
        responses={
            200: ServiceSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Services - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete service",
        description="""
        Delete a service (salon owners only).
        
        **Restrictions:**
        - Cannot delete if there are pending or confirmed bookings for this service
        - Complete or cancel active bookings first, then delete
        """,
        responses={
            204: OpenApiResponse(description="Service deleted successfully"),
            400: OpenApiResponse(description="Bad Request - Has active bookings"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Services - Client']
    )
    def destroy(self, request, *args, **kwargs):
        service = self.get_object()
        
        # Check for active bookings (pending or confirmed)
        from apps.bookings.models import Booking
        active_bookings = Booking.objects.filter(
            service=service,
            status__in=['pending', 'confirmed']
        )
        
        active_count = active_bookings.count()
        if active_count > 0:
            # Get upcoming booking details
            upcoming = active_bookings.order_by('booking_datetime').first()
            return Response(
                {
                    'error': 'Cannot delete service with active bookings',
                    'active_bookings_count': active_count,
                    'message': f'There are {active_count} pending/confirmed booking(s) for this service. Complete or cancel them first.',
                    'next_booking': {
                        'id': str(upcoming.id),
                        'datetime': upcoming.booking_datetime.isoformat(),
                        'customer': upcoming.customer.user.full_name if upcoming.customer else 'Unknown'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        summary="Toggle service active status",
        description="Enable or disable a service (salon owners only)",
        request=None,
        responses={
            200: ServiceSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Services - Client']
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsClient, IsShopOwner])
    def toggle_active(self, request, pk=None):
        """Toggle service active status"""
        service = self.get_object()
        service.is_active = not service.is_active
        service.save(update_fields=['is_active'])
        return Response(ServiceSerializer(service).data)
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_active']:
            return [IsClient(), IsShopOwner()]
        return super().get_permissions()
