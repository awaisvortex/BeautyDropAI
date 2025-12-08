"""
Booking views - COMPLETE AND FIXED
"""
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.utils import timezone
from django.db.models import Sum, Q

from apps.core.permissions import IsCustomer, IsClient, IsBookingOwner
from .models import Booking
from .serializers import (
    BookingSerializer,
    BookingListSerializer,
    BookingStatsSerializer,
    DynamicBookingCreateSerializer
)


class BookingViewSet(viewsets.GenericViewSet, 
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin):
    """
    ViewSet for managing bookings.
    
    Create bookings with dynamic_book (recommended).
    Use cancel instead of destroy for proper booking lifecycle.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'shop', 'service']
    ordering_fields = ['booking_datetime', 'created_at', 'total_price']
    ordering = ['-booking_datetime']
    
    def get_serializer_class(self):
        if self.action == 'list' or 'bookings' in self.action:
            return BookingListSerializer
        elif self.action == 'stats':
            return BookingStatsSerializer
        return BookingSerializer
    
    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        
        user = self.request.user
        
        # Handle anonymous users
        if not user.is_authenticated:
            return Booking.objects.none()
        
        queryset = Booking.objects.select_related(
            'customer__user', 'shop__client__user', 'service', 'time_slot', 'staff_member'
        )
        
        # Customers see their own bookings
        if user.role == 'customer':
            queryset = queryset.filter(customer__user=user)
        
        # Clients see bookings for their shops
        elif user.role == 'client':
            queryset = queryset.filter(shop__client__user=user)
        
        return queryset
    
    @extend_schema(
        summary="List bookings",
        description="Get bookings. Customers see their bookings, salon owners see their shop bookings.",
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('shop', str, description='Filter by shop UUID'),
            OpenApiParameter('service', str, description='Filter by service UUID'),
        ],
        responses={200: BookingListSerializer(many=True)},
        tags=['Bookings - Customer']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get booking details",
        description="Retrieve detailed information about a specific booking",
        responses={
            200: BookingSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Customer']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="My bookings",
        description="Get current customer's booking history",
        responses={200: BookingListSerializer(many=True)},
        tags=['Bookings - Customer']
    )
    @action(detail=False, methods=['get'], permission_classes=[IsCustomer])
    def my_bookings(self, request):
        """Get customer's bookings"""
        bookings = self.get_queryset()
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Dynamic booking (no TimeSlot required)",
        description="""
        Create a booking without requiring a pre-created TimeSlot.
        
        Uses dynamic availability to validate the slot and create the booking.
        This is the recommended endpoint for new booking implementations.
        
        The system will:
        1. Validate the slot is within shop hours
        2. Check staff availability for the requested time
        3. Auto-assign or use specified staff member
        4. Create the booking directly
        """,
        request=DynamicBookingCreateSerializer,
        examples=[
            OpenApiExample(
                'Dynamic Booking Example',
                value={
                    'service_id': 'd241ec69-f739-4040-94a0-b46286742dbe',
                    'date': '2024-12-10',
                    'start_time': '10:00',
                    'staff_member_id': 'b9743cc7-1364-4a32-a3b7-730a02365f00',
                    'notes': 'Please call me when you arrive'
                },
                request_only=True
            )
        ],
        responses={
            201: BookingSerializer,
            400: OpenApiResponse(description="Bad Request - Slot not available or invalid data"),
            403: OpenApiResponse(description="Forbidden - Only customers can create bookings")
        },
        tags=['Bookings - Customer']
    )
    @action(detail=False, methods=['post'], permission_classes=[IsCustomer])
    def dynamic_book(self, request):
        """
        Create a booking using dynamic availability.
        No pre-created TimeSlot required.
        """
        if request.user.role != 'customer':
            return Response(
                {'error': 'Only customers can create bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get or create customer profile
        from apps.customers.models import Customer
        customer, created = Customer.objects.get_or_create(user=request.user)
        
        serializer = DynamicBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = serializer.validated_data['service']
        booking_datetime = serializer.validated_data['booking_datetime']
        target_date = serializer.validated_data['date']
        staff_member_id = serializer.validated_data.get('staff_member_id')
        
        # Use AvailabilityService to check if this slot is actually available
        from apps.schedules.services.availability import AvailabilityService
        from apps.staff.models import StaffMember, StaffService
        from datetime import timedelta
        
        availability_service = AvailabilityService(
            service_id=service.id,
            target_date=target_date,
            buffer_minutes=15
        )
        
        # Check if shop is open
        if not availability_service.is_shop_open():
            return Response(
                {'error': 'Shop is closed on this date'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get available slots and check if requested time is valid
        available_slots = availability_service.get_available_slots()
        
        # Check if no slots are available due to no staff assigned
        if not available_slots:
            eligible_staff = availability_service._get_eligible_staff()
            if not eligible_staff.exists():
                return Response(
                    {'error': 'No staff available for this service. Please assign staff members to this service first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Otherwise, shop is closed or all slots are booked
            return Response(
                {'error': 'This time slot is not available. Please check available slots first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the slot that matches the requested time
        matching_slot = None
        for slot in available_slots:
            if slot.start_time == booking_datetime:
                matching_slot = slot
                break
        
        if not matching_slot:
            return Response(
                {'error': 'This time slot is not available. Please check available slots first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle staff member assignment
        staff_member = None
        
        if staff_member_id:
            # User selected specific staff - verify they're in available_staff_ids
            if staff_member_id not in matching_slot.available_staff_ids:
                return Response(
                    {'error': 'Selected staff member is not available at this time'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            staff_member = StaffMember.objects.get(id=staff_member_id)
        else:
            # Auto-assign from available staff
            if matching_slot.available_staff_ids:
                available_staff = StaffMember.objects.filter(
                    id__in=matching_slot.available_staff_ids
                )
                
                # Try primary staff for this service first
                primary = StaffService.objects.filter(
                    service=service,
                    is_primary=True,
                    staff_member__in=available_staff
                ).first()
                if primary:
                    staff_member = primary.staff_member
                else:
                    # Any available staff
                    staff_member = available_staff.first()
        
        # Calculate end time
        booking_end = booking_datetime + timedelta(minutes=service.duration_minutes)
        
        # Create booking (no TimeSlot needed)
        booking = Booking.objects.create(
            customer=customer,
            shop=service.shop,
            service=service,
            time_slot=None,  # Dynamic booking - no TimeSlot
            staff_member=staff_member,
            booking_datetime=booking_datetime,
            total_price=service.price,
            notes=serializer.validated_data.get('notes', ''),
            status='pending'
        )
        
        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Shop bookings",
        description="Get all bookings for a specific shop (salon owners only)",
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
        ],
        responses={200: BookingListSerializer(many=True)},
        tags=['Bookings - Client']
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsClient],
        url_path='shop/(?P<shop_id>[^/.]+)'
    )
    def shop_bookings(self, request, shop_id=None):
        """Get bookings for a specific shop"""
        bookings = self.get_queryset().filter(shop_id=shop_id)
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Today's bookings",
        description="Get today's bookings for a shop (salon owners only)",
        responses={200: BookingListSerializer(many=True)},
        tags=['Bookings - Client']
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsClient],
        url_path='shop/(?P<shop_id>[^/.]+)/today'
    )
    def today_bookings(self, request, shop_id=None):
        """Get today's bookings for a shop"""
        today = timezone.now().date()
        bookings = self.get_queryset().filter(
            shop_id=shop_id,
            booking_datetime__date=today
        )
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Upcoming bookings",
        description="Get upcoming bookings for a shop (salon owners only)",
        responses={200: BookingListSerializer(many=True)},
        tags=['Bookings - Client']
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsClient],
        url_path='shop/(?P<shop_id>[^/.]+)/upcoming'
    )
    def upcoming_bookings(self, request, shop_id=None):
        """Get upcoming bookings for a shop"""
        now = timezone.now()
        bookings = self.get_queryset().filter(
            shop_id=shop_id,
            booking_datetime__gte=now,
            status__in=['pending', 'confirmed']
        )
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Cancel booking",
        description="Cancel a booking",
        request=None,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request - Cannot cancel this booking"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Customer']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsBookingOwner])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        if booking.status in ['completed', 'cancelled', 'no_show']:
            return Response(
                {'error': f'Cannot cancel a booking with status: {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save(update_fields=['status'])
        
        # Free up the time slot
        if booking.time_slot:
            booking.time_slot.status = 'available'
            booking.time_slot.save(update_fields=['status'])
        
        return Response(BookingSerializer(booking).data)
    
    @extend_schema(
        summary="Confirm booking",
        description="Confirm a booking (salon owners only)",
        request=None,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsBookingOwner])
    def confirm(self, request, pk=None):
        """Confirm a booking"""
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response(
                {'error': 'Only pending bookings can be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'confirmed'
        booking.save(update_fields=['status'])
        return Response(BookingSerializer(booking).data)
    
    @extend_schema(
        summary="Complete booking",
        description="Mark booking as completed (salon owners only)",
        request=None,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsBookingOwner])
    def complete(self, request, pk=None):
        """Complete a booking"""
        booking = self.get_object()
        
        if booking.status not in ['pending', 'confirmed']:
            return Response(
                {'error': 'Only pending or confirmed bookings can be completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'completed'
        booking.save(update_fields=['status'])
        return Response(BookingSerializer(booking).data)
    
    @extend_schema(
        summary="Mark as no-show",
        description="Mark booking as no-show (salon owners only)",
        request=None,
        responses={
            200: BookingSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsBookingOwner])
    def no_show(self, request, pk=None):
        """Mark booking as no-show"""
        booking = self.get_object()
        booking.status = 'no_show'
        booking.save(update_fields=['status'])
        
        # Free up the time slot
        if booking.time_slot:
            booking.time_slot.status = 'available'
            booking.time_slot.save(update_fields=['status'])
        
        return Response(BookingSerializer(booking).data)
    
    @extend_schema(
        summary="Booking statistics",
        description="Get booking statistics for a shop (salon owners only)",
        responses={200: BookingStatsSerializer},
        tags=['Bookings - Client']
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsClient],
        url_path='shop/(?P<shop_id>[^/.]+)/stats'
    )
    def stats(self, request, shop_id=None):
        """Get booking statistics for a shop"""
        bookings = self.get_queryset().filter(shop_id=shop_id)
        
        total_bookings = bookings.count()
        pending = bookings.filter(status='pending').count()
        confirmed = bookings.filter(status='confirmed').count()
        completed = bookings.filter(status='completed').count()
        cancelled = bookings.filter(status='cancelled').count()
        no_show = bookings.filter(status='no_show').count()
        
        total_revenue = bookings.filter(status='completed').aggregate(
            total=Sum('total_price')
        )['total'] or 0
        
        stats = {
            'total_bookings': total_bookings,
            'pending': pending,
            'confirmed': confirmed,
            'completed': completed,
            'cancelled': cancelled,
            'no_show': no_show,
            'total_revenue': float(total_revenue)
        }
        
        return Response(stats)
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['my_bookings', 'dynamic_book']:
            return [IsCustomer()]
        elif self.action in ['shop_bookings', 'today_bookings', 'upcoming_bookings', 'confirm', 'complete', 'no_show', 'stats']:
            return [IsClient()]
        elif self.action == 'cancel':
            return [IsAuthenticated(), IsBookingOwner()]
        return super().get_permissions()
