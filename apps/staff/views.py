"""
Staff views
"""
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.permissions import IsClient, IsShopOwner
from .models import StaffMember, StaffService
from .serializers import (
    StaffMemberSerializer,
    StaffMemberCreateUpdateSerializer,
    StaffMemberDetailSerializer,
    StaffServiceAssignmentSerializer
)


class StaffMemberViewSet(viewsets.ModelViewSet):
    """ViewSet for managing staff members"""
    queryset = StaffMember.objects.select_related('shop').prefetch_related('staff_services__service')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'is_active']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StaffMemberDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return StaffMemberCreateUpdateSerializer
        return StaffMemberSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Handle unauthenticated users (public access for viewing)
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_active=True)
        # Clients see only their shop's staff
        elif self.request.user.is_authenticated and self.request.user.role == 'client':
            if self.action not in ['list', 'retrieve', 'available_for_service']:
                queryset = queryset.filter(shop__client__user=self.request.user)
        # Customers see only active staff
        elif self.request.user.is_authenticated and self.request.user.role == 'customer':
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @extend_schema(
        summary="List staff members",
        description="Get all staff members. Filter by shop_id to get staff for a specific shop. Public endpoint.",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
            OpenApiParameter('is_active', bool, description='Filter by active status'),
            OpenApiParameter('search', str, description='Search in name, email, phone'),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get staff member details",
        description="Retrieve detailed information about a specific staff member including assigned services. Public endpoint.",
        responses={
            200: StaffMemberDetailSerializer,
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create staff member",
        description="Add a new staff member to a shop (salon owners only). Requires shop_id in request body.",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            201: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden - Only salon owners can create staff")
        },
        tags=['Staff - Client']
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != 'client':
            return Response(
                {'error': 'Only salon owners can create staff members'},
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
        
        staff_member = serializer.save(shop=shop)
        return Response(
            StaffMemberSerializer(staff_member).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Update staff member",
        description="Update staff member details (salon owners only)",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            200: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update staff member",
        description="Partially update staff member details (salon owners only)",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            200: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete staff member",
        description="Remove a staff member from a shop (salon owners only)",
        responses={
            204: OpenApiResponse(description="Staff member deleted successfully"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        summary="Toggle staff availability",
        description="Mark staff as available or unavailable (e.g., for sick days, days off). Salon owners only.",
        request=None,
        responses={
            200: StaffMemberSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsClient, IsShopOwner])
    def toggle_availability(self, request, pk=None):
        """Toggle staff availability status"""
        staff_member = self.get_object()
        staff_member.is_active = not staff_member.is_active
        staff_member.save(update_fields=['is_active'])
        
        return Response(
            StaffMemberSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Assign services to staff",
        description="Assign one or more services to a staff member. Can mark staff as primary for specific services (salon owners only).",
        request=StaffServiceAssignmentSerializer,
        responses={
            200: StaffMemberDetailSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member or service not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def assign_services(self, request, pk=None):
        """Assign services to a staff member"""
        staff_member = self.get_object()
        serializer = StaffServiceAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service_ids = serializer.validated_data['service_ids']
        is_primary = serializer.validated_data.get('is_primary', False)
        
        # Verify all services belong to the same shop
        from apps.services.models import Service
        services = Service.objects.filter(id__in=service_ids, shop=staff_member.shop)
        
        if services.count() != len(service_ids):
            return Response(
                {'error': 'One or more services not found or do not belong to this shop'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Assign services
        for service in services:
            StaffService.objects.update_or_create(
                staff_member=staff_member,
                service=service,
                defaults={'is_primary': is_primary}
            )
        
        return Response(
            StaffMemberDetailSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Remove service from staff",
        description="Remove a service assignment from a staff member (salon owners only)",
        parameters=[
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Service ID to remove', required=True),
        ],
        responses={
            200: StaffMemberDetailSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member or service not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['delete'], permission_classes=[IsClient, IsShopOwner])
    def remove_service(self, request, pk=None):
        """Remove a service from a staff member"""
        staff_member = self.get_object()
        service_id = request.query_params.get('service_id')
        
        if not service_id:
            return Response(
                {'error': 'service_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            staff_service = StaffService.objects.get(
                staff_member=staff_member,
                service_id=service_id
            )
            staff_service.delete()
        except StaffService.DoesNotExist:
            return Response(
                {'error': 'Service assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            StaffMemberDetailSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Get available staff for time slot",
        description="Get all staff members available for a specific time slot (not already booked). Optionally filter by service. Public endpoint for customer booking.",
        parameters=[
            OpenApiParameter('time_slot_id', OpenApiTypes.UUID, description='Time Slot ID', required=True),
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Optional: Filter by service ID'),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def available_for_time_slot(self, request):
        """Get staff members available for a specific time slot"""
        from apps.schedules.models import TimeSlot
        from apps.bookings.models import Booking
        
        time_slot_id = request.query_params.get('time_slot_id')
        service_id = request.query_params.get('service_id')
        
        if not time_slot_id:
            return Response(
                {'error': 'time_slot_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
        except TimeSlot.DoesNotExist:
            return Response(
                {'error': 'Time slot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all active staff for this shop
        all_staff = StaffMember.objects.filter(
            shop=time_slot.schedule.shop,
            is_active=True
        )
        
        # Filter by service if provided
        if service_id:
            # Include staff with no service assignments (free staff) OR staff assigned to this service
            all_staff = all_staff.filter(
                models.Q(services__id=service_id) | models.Q(services__isnull=True)
            ).distinct()
        
        # Exclude staff who are already booked for this time slot
        available_staff_ids = []
        for staff in all_staff:
            conflicting_booking = Booking.objects.filter(
                staff_member=staff,
                time_slot__start_datetime__lt=time_slot.end_datetime,
                time_slot__end_datetime__gt=time_slot.start_datetime,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if not conflicting_booking:
                available_staff_ids.append(staff.id)
        
        available_staff = StaffMember.objects.filter(id__in=available_staff_ids)
        serializer = StaffMemberSerializer(available_staff, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get available staff for service",
        description="Get all staff members who can provide a specific service. Public endpoint for customer booking.",
        parameters=[
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Service ID', required=True),
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Shop ID', required=True),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def available_for_service(self, request):
        """Get staff members available for a specific service"""
        service_id = request.query_params.get('service_id')
        shop_id = request.query_params.get('shop_id')
        
        if not service_id or not shop_id:
            return Response(
                {'error': 'Both service_id and shop_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get staff members who can provide this service (including free staff)
        from django.db import models
        staff_members = StaffMember.objects.filter(
            shop_id=shop_id,
            is_active=True
        ).filter(
            models.Q(services__id=service_id) | models.Q(services__isnull=True)
        ).distinct()
        
        serializer = StaffMemberSerializer(staff_members, many=True)
        return Response(serializer.data)
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'available_for_service', 'available_for_time_slot']:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_availability', 'assign_services', 'remove_service']:
            return [IsClient(), IsShopOwner()]
        return super().get_permissions()
