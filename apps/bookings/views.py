"""
Booking views - COMPLETE AND FIXED
"""
from rest_framework import viewsets, status
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
    BookingCreateSerializer,
    BookingListSerializer,
    BookingUpdateStatusSerializer,
    BookingRescheduleSerializer,
    BookingStatsSerializer
)


class BookingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing bookings"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'shop', 'service']
    ordering_fields = ['booking_datetime', 'created_at', 'total_price']
    ordering = ['-booking_datetime']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action == 'list' or 'bookings' in self.action:
            return BookingListSerializer
        elif self.action == 'update_status':
            return BookingUpdateStatusSerializer
        elif self.action == 'reschedule':
            return BookingRescheduleSerializer
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
        summary="Create booking",
        description="Create a new booking (customers only)",
        request=BookingCreateSerializer,
        examples=[
            OpenApiExample(
                'Booking Creation Example',
                value={
                    'service_id': 'd241ec69-f739-4040-94a0-b46286742dbe',
                    'time_slot_id': '3108e310-9780-448f-809d-d014e7d716b8',
                    'staff_member_id': 'b9743cc7-1364-4a32-a3b7-730a02365f00',
                    'notes': 'Please call me when you arrive'
                },
                request_only=True
            )
        ],
        responses={
            201: BookingSerializer,
            400: OpenApiResponse(description="Bad Request - Invalid data or time slot not available"),
            403: OpenApiResponse(description="Forbidden - Only customers can create bookings")
        },
        tags=['Bookings - Customer']
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != 'customer':
            return Response(
                {'error': 'Only customers can create bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get or create customer profile
        from apps.customers.models import Customer
        customer, created = Customer.objects.get_or_create(user=request.user)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get validated data
        from apps.services.models import Service
        from apps.schedules.models import TimeSlot
        from apps.staff.models import StaffMember, StaffService
        
        service = Service.objects.get(id=serializer.validated_data['service_id'])
        time_slot = TimeSlot.objects.get(id=serializer.validated_data['time_slot_id'])
        
        # Handle staff member assignment with availability checking
        staff_member = None
        staff_member_id = serializer.validated_data.get('staff_member_id')
        
        if staff_member_id:
            # User selected a specific staff member - verify availability
            try:
                staff_member = StaffMember.objects.get(
                    id=staff_member_id,
                    shop=service.shop,
                    is_active=True
                )
                
                # Check if staff member is already booked for this time slot
                conflicting_booking = Booking.objects.filter(
                    staff_member=staff_member,
                    time_slot__start_datetime__lt=time_slot.end_datetime,
                    time_slot__end_datetime__gt=time_slot.start_datetime,
                    status__in=['pending', 'confirmed']
                ).exists()
                
                if conflicting_booking:
                    return Response(
                        {'error': f'{staff_member.name} is already booked for this time slot'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Verify staff can provide this service (if they have service assignments)
                staff_services = staff_member.services.all()
                if staff_services.exists() and not staff_services.filter(id=service.id).exists():
                    return Response(
                        {'error': f'{staff_member.name} cannot provide this service'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except StaffMember.DoesNotExist:
                return Response(
                    {'error': 'Selected staff member not found or not available'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Auto-assign staff member with smart prioritization
            # Get all active staff for this shop
            all_staff = StaffMember.objects.filter(
                shop=service.shop,
                is_active=True
            )
            
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
            
            # Priority 1: Free staff (no specific service assignments) who are available
            free_staff = available_staff.filter(services__isnull=True).first()
            
            if free_staff:
                staff_member = free_staff
            else:
                # Priority 2: Staff marked as primary for this service
                primary_staff = StaffService.objects.filter(
                    service=service,
                    is_primary=True,
                    staff_member__in=available_staff
                ).first()
                
                if primary_staff:
                    staff_member = primary_staff.staff_member
                else:
                    # Priority 3: Any available staff who can provide this service
                    service_staff = available_staff.filter(services=service).first()
                    
                    if service_staff:
                        staff_member = service_staff
                    else:
                        # Priority 4: Check if time slot has pre-assigned staff
                        if time_slot.staff_member and time_slot.staff_member.id in available_staff_ids:
                            staff_member = time_slot.staff_member
        
        # Create booking
        booking = Booking.objects.create(
            customer=customer,
            shop=service.shop,
            service=service,
            time_slot=time_slot,
            staff_member=staff_member,
            booking_datetime=time_slot.start_datetime,
            total_price=service.price,
            notes=serializer.validated_data.get('notes', ''),
            status='pending'
        )
        
        # Mark time slot as booked
        time_slot.status = 'booked'
        time_slot.save(update_fields=['status'])
        
        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Update booking",
        description="Update booking details (salon owners only)",
        request=BookingCreateSerializer,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update booking",
        description="Partially update booking details (salon owners only)",
        request=BookingCreateSerializer,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete booking",
        description="Delete a booking (salon owners only)",
        responses={
            204: OpenApiResponse(description="Booking deleted successfully"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
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
        request=BookingUpdateStatusSerializer,
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
        summary="Reschedule booking",
        description="Reschedule a booking to a new time slot",
        request=BookingRescheduleSerializer,
        examples=[
            OpenApiExample(
                'Reschedule Example',
                value={
                    'new_time_slot_id': '3108e310-9780-448f-809d-d014e7d716b8'
                },
                request_only=True
            )
        ],
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Customer']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsBookingOwner])
    def reschedule(self, request, pk=None):
        """Reschedule a booking"""
        booking = self.get_object()
        
        if booking.status not in ['pending', 'confirmed']:
            return Response(
                {'error': 'Only pending or confirmed bookings can be rescheduled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = BookingRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from apps.schedules.models import TimeSlot
        new_time_slot = TimeSlot.objects.get(id=serializer.validated_data['new_time_slot_id'])
        
        if new_time_slot.status != 'available':
            return Response(
                {'error': 'Selected time slot is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Free old time slot
        if booking.time_slot:
            booking.time_slot.status = 'available'
            booking.time_slot.save(update_fields=['status'])
        
        # Update booking
        booking.time_slot = new_time_slot
        booking.booking_datetime = new_time_slot.start_datetime
        booking.save(update_fields=['time_slot', 'booking_datetime'])
        
        # Mark new time slot as booked
        new_time_slot.status = 'booked'
        new_time_slot.save(update_fields=['status'])
        
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
        if self.action in ['create', 'my_bookings']:
            return [IsCustomer()]
        elif self.action in ['shop_bookings', 'today_bookings', 'upcoming_bookings', 'confirm', 'complete', 'no_show', 'stats']:
            return [IsClient()]
        elif self.action in ['cancel', 'reschedule']:
            return [IsAuthenticated(), IsBookingOwner()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsClient(), IsBookingOwner()]
        return super().get_permissions()
