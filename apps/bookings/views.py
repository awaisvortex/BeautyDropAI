"""
Booking views - COMPLETE AND FIXED
"""
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.utils import timezone
from django.db.models import Sum, Q

from apps.core.permissions import IsCustomer, IsClient, IsBookingOwner
from apps.payments.booking_payment_service import booking_payment_service
from .models import Booking
from .serializers import (
    BookingSerializer,
    BookingListSerializer,
    BookingStatsSerializer,
    DynamicBookingCreateSerializer,
    OwnerRescheduleSerializer,
    StaffReassignSerializer,
    StaffReassignResponseSerializer,
    OwnerRescheduleResponseSerializer,
    DealSlotSerializer,
    DealAvailabilitySerializer,
    DealBookingCreateSerializer,
    BookingWithPaymentResponseSerializer,
    PaymentInfoSerializer
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
            'customer__user', 'shop__client__user', 'service', 'deal', 'time_slot', 'staff_member'
        )
        
        # Customers see their own bookings
        if user.role == 'customer':
            queryset = queryset.filter(customer__user=user)
        
        # Clients see bookings for their shops
        elif user.role == 'client':
            queryset = queryset.filter(shop__client__user=user)
        
        # Staff see only their assigned bookings
        elif user.role == 'staff':
            staff_profile = getattr(user, 'staff_profile', None)
            if staff_profile:
                queryset = queryset.filter(staff_member=staff_profile)
            else:
                queryset = queryset.none()
        
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
        summary="My booking stats",
        description="Get current customer's booking statistics including upcoming count",
        responses={200: dict},
        tags=['Bookings - Customer']
    )
    @action(detail=False, methods=['get'], permission_classes=[IsCustomer])
    def my_stats(self, request):
        """Get customer's booking statistics"""
        bookings = self.get_queryset()
        now = timezone.now()
        
        # Upcoming = future bookings that are pending or confirmed
        upcoming = bookings.filter(
            booking_datetime__gte=now,
            status__in=['pending', 'confirmed']
        ).count()
        
        # Past due = past bookings that are still pending/confirmed (should be completed/no_show)
        past_due = bookings.filter(
            booking_datetime__lt=now,
            status__in=['pending', 'confirmed']
        ).count()
        
        # Completed
        completed = bookings.filter(status='completed').count()
        
        # Cancelled
        cancelled = bookings.filter(status='cancelled').count()
        
        # Total
        total = bookings.count()
        
        return Response({
            'upcoming': upcoming,
            'past_due': past_due,
            'completed': completed,
            'cancelled': cancelled,
            'total': total
        })
    
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
        4. Create the booking with 'pending' status
        5. Create a payment intent if Stripe Connect is enabled
        
        **Payment Flow:**
        - If shop owner has Stripe Connect enabled: Returns `client_secret` for payment
        - If shop doesn't have Stripe Connect: Booking is auto-confirmed
        - If advance payment is disabled: Booking is auto-confirmed
        
        **Response includes:**
        - Booking details
        - Payment object with either:
          - `client_secret` for Stripe.js (when payment required)
          - Confirmation message (when no payment required)
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
            ),
            OpenApiExample(
                'Response with Payment Required',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'status': 'pending',
                    'service': {'id': 'd241ec69...', 'name': 'Haircut'},
                    'booking_datetime': '2024-12-10T10:00:00Z',
                    'total_price': '50.00',
                    'payment': {
                        'required': True,
                        'client_secret': 'pi_xxx_secret_yyy',
                        'payment_intent_id': 'pi_xxx',
                        'amount': 5.0,
                        'amount_cents': 500,
                        'currency': 'usd',
                        'message': 'Your slot is reserved for 15 minutes. Please complete payment within this time to confirm your booking.'
                    }
                },
                response_only=True
            ),
            OpenApiExample(
                'Response without Payment Required',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'status': 'confirmed',
                    'service': {'id': 'd241ec69...', 'name': 'Haircut'},
                    'booking_datetime': '2024-12-10T10:00:00Z',
                    'total_price': '50.00',
                    'payment': {
                        'required': False,
                        'message': 'Shop payment setup incomplete - booking created without deposit'
                    }
                },
                response_only=True
            )
        ],
        responses={
            201: BookingWithPaymentResponseSerializer,
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
                {'error': 'No available slots on this date. The shop may be closed or fully booked.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert booking_datetime to shop's timezone for accurate comparison
        # AvailabilityService returns slots in shop's timezone
        import pytz
        try:
            shop_tz = pytz.timezone(service.shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        booking_datetime_shop_tz = booking_datetime.astimezone(shop_tz)
        
        # Find the slot that matches the requested time
        matching_slot = None
        for slot in available_slots:
            # Both should now be in shop timezone for comparison
            slot_time_normalized = slot.start_time.astimezone(shop_tz)
            if slot_time_normalized == booking_datetime_shop_tz:
                matching_slot = slot
                break
        
        if not matching_slot:
            # Provide helpful debug info
            available_times = [s.start_time.astimezone(shop_tz).strftime('%H:%M') for s in available_slots[:5]]
            return Response(
                {
                    'error': 'This time slot is not available. Please check available slots first.',
                    'requested_time': booking_datetime_shop_tz.strftime('%Y-%m-%d %H:%M %Z'),
                    'sample_available_times': available_times
                },
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
        # Initial status is 'pending' - will be confirmed after payment (if required)
        booking = Booking.objects.create(
            customer=customer,
            shop=service.shop,
            service=service,
            time_slot=None,  # Dynamic booking - no TimeSlot
            staff_member=staff_member,
            booking_datetime=booking_datetime,
            duration_minutes=service.duration_minutes,
            total_price=service.price,
            notes=serializer.validated_data.get('notes', ''),
            status='pending'
        )
        
        # Attempt to create advance payment
        payment_result = booking_payment_service.create_advance_payment(booking)
        
        # Build response
        response_data = BookingSerializer(booking).data
        
        if payment_result.get('payment_required'):
            # Payment is required - return client_secret for Stripe.js
            response_data['payment'] = {
                'required': True,
                'client_secret': payment_result['client_secret'],
                'payment_intent_id': payment_result['payment_intent_id'],
                'amount': float(payment_result['amount']),
                'amount_cents': payment_result['amount_cents'],
                'currency': payment_result['currency'],
                'message': 'Your slot is reserved for 15 minutes. Please complete payment within this time to confirm your booking.'
            }
            
            # Schedule auto-cancellation after 15 minutes if payment not completed
            from apps.bookings.tasks import cancel_unpaid_booking
            cancel_unpaid_booking.apply_async(
                args=[str(booking.id)],
                countdown=15 * 60  # 15 minutes in seconds
            )
        else:
            # Payment not required - booking auto-confirmed
            response_data['payment'] = {
                'required': False,
                'message': payment_result.get('message', 'No advance payment required')
            }
        
        return Response(
            response_data,
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
        
        # Determine who is cancelling based on user role
        user = request.user
        if user.role == 'customer':
            cancelled_by = 'customer'
        elif user.role == 'staff':
            cancelled_by = 'staff'
        elif user.role == 'client':
            cancelled_by = 'owner'
        else:
            cancelled_by = 'system'
        
        # Get cancellation reason from request body if provided
        cancellation_reason = request.data.get('reason', '')
        
        booking.status = 'cancelled'
        booking.cancelled_by = cancelled_by
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = cancellation_reason
        booking.save(update_fields=['status', 'cancelled_by', 'cancelled_at', 'cancellation_reason'])
        
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
        """
        Confirm a booking.
        
        Behavior depends on shop's Stripe Connect status:
        - No Stripe Connect: Manual confirmation allowed (old flow)
        - Stripe Connect active: Blocked until customer pays advance payment
        """
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response(
                {'error': 'Only pending bookings can be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if shop owner has Stripe Connect set up
        from apps.payments.models import ConnectedAccount
        shop_has_stripe_connect = False
        try:
            connected_account = booking.shop.client.connected_account
            shop_has_stripe_connect = connected_account.is_ready_for_payments
        except ConnectedAccount.DoesNotExist:
            pass
        
        # If Stripe Connect is NOT set up, allow manual confirmation (old flow)
        if not shop_has_stripe_connect:
            booking.status = 'confirmed'
            booking.save(update_fields=['status'])
            return Response(BookingSerializer(booking).data)
        
        # Stripe Connect IS set up - require advance payment before confirmation
        # payment_status options: 'pending', 'paid', 'not_required', 'refunded', 'failed'
        if booking.payment_status == 'pending':
            return Response(
                {
                    'error': 'Booking requires advance payment before confirmation. Customer has not paid yet.',
                    'payment_status': booking.payment_status,
                    'stripe_connect_active': True,
                    'message': 'With Stripe Connect enabled, bookings are auto-confirmed when customer pays.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Payment is either 'paid' or 'not_required' - allow confirmation
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
    
    @extend_schema(
        summary="Reschedule booking (Owner)",
        description="""
        Reschedule a booking to a new date/time.
        
        **Validation:**
        - Date cannot be in the past
        - Shop must be open on the new date
        - New time slot must be available
        - If assigned staff is not available at new time, will auto-reassign to available staff
        """,
        request=OwnerRescheduleSerializer,
        examples=[
            OpenApiExample(
                'Reschedule Booking',
                value={
                    'date': '2024-12-20',
                    'start_time': '14:00'
                },
                request_only=True
            )
        ],
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Bad Request - Slot not available or shop closed"),
            403: OpenApiResponse(description="Forbidden - Not shop owner"),
            404: OpenApiResponse(description="Booking not found")
        },
        tags=['Bookings - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient])
    def reschedule(self, request, pk=None):
        """Reschedule a booking to a new date/time (shop owner only)."""
        booking = self.get_object()
        
        # Verify shop ownership
        if booking.shop.client.user != request.user:
            return Response(
                {'error': 'You do not own this shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cannot reschedule completed/cancelled bookings
        if booking.status in ['completed', 'cancelled', 'no_show']:
            return Response(
                {'error': f'Cannot reschedule a booking with status: {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OwnerRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_date = serializer.validated_data['date']
        new_time = serializer.validated_data['start_time']
        
        from datetime import datetime, timedelta
        import pytz
        
        # Get shop's timezone
        try:
            shop_tz = pytz.timezone(booking.shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        # Create new booking datetime
        naive_datetime = datetime.combine(new_date, new_time)
        new_booking_datetime = shop_tz.localize(naive_datetime)
        
        # DEAL BOOKING - simpler capacity-based validation
        if booking.is_deal_booking:
            from apps.schedules.models import ShopSchedule
            
            # Check shop is open
            day_name = new_date.strftime('%A').lower()
            try:
                schedule = ShopSchedule.objects.get(shop=booking.shop, day_of_week=day_name)
            except ShopSchedule.DoesNotExist:
                return Response(
                    {'error': 'Shop has no schedule for this day'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not schedule.is_active:
                return Response(
                    {'error': 'Shop is closed on this day'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check time is within shop hours
            shop_open = shop_tz.localize(datetime.combine(new_date, schedule.start_time))
            shop_close = shop_tz.localize(datetime.combine(new_date, schedule.end_time))
            slot_end = new_booking_datetime + timedelta(minutes=booking.duration_minutes)
            
            if new_booking_datetime < shop_open or slot_end > shop_close:
                return Response(
                    {'error': 'Time is outside shop hours'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check capacity at new time (exclude current booking)
            max_concurrent = booking.shop.max_concurrent_deal_bookings
            existing_bookings = Booking.objects.filter(
                shop=booking.shop,
                deal__isnull=False,
                status__in=['pending', 'confirmed'],
                booking_datetime__date=new_date
            ).exclude(id=booking.id)
            
            overlapping = 0
            for existing in existing_bookings:
                existing_end = existing.booking_datetime + timedelta(minutes=existing.duration_minutes)
                if existing.booking_datetime < slot_end and existing_end > new_booking_datetime:
                    overlapping += 1
            
            if overlapping >= max_concurrent:
                return Response(
                    {'error': 'Maximum capacity reached at this time', 'slots_left': 0},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update booking datetime (no staff for deals)
            booking.booking_datetime = new_booking_datetime
            booking.save(update_fields=['booking_datetime'])
            
            return Response(BookingSerializer(booking).data)
        
        # SERVICE BOOKING - use AvailabilityService
        from apps.schedules.services.availability import AvailabilityService
        
        availability_service = AvailabilityService(
            service_id=booking.service.id,
            target_date=new_date,
            buffer_minutes=0  # No buffer for owner rescheduling
        )
        
        # Check if shop is open
        if not availability_service.is_shop_open():
            return Response(
                {'error': 'Shop is closed on this date'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get available slots
        available_slots = availability_service.get_available_slots()
        
        if not available_slots:
            return Response(
                {'error': 'No available slots on this date'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if requested time is available
        matching_slot = None
        for slot in available_slots:
            slot_time = slot.start_time.astimezone(shop_tz)
            if slot_time == new_booking_datetime:
                matching_slot = slot
                break
        
        if not matching_slot:
            return Response(
                {'error': 'This time slot is not available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update booking datetime
        booking.booking_datetime = new_booking_datetime
        
        # If current staff is not available at new time, reassign
        if booking.staff_member_id and booking.staff_member_id not in matching_slot.available_staff_ids:
            from apps.staff.models import StaffMember, StaffService
            # Try to use primary staff for service
            primary = StaffService.objects.filter(
                service=booking.service,
                is_primary=True,
                staff_member_id__in=matching_slot.available_staff_ids
            ).first()
            if primary:
                booking.staff_member = primary.staff_member
            elif matching_slot.available_staff_ids:
                booking.staff_member = StaffMember.objects.get(id=matching_slot.available_staff_ids[0])
        
        booking.save(update_fields=['booking_datetime', 'staff_member'])
        
        return Response(BookingSerializer(booking).data)
    
    @extend_schema(
        summary="Reassign staff (Owner)",
        description="""
        Reassign a booking to a different staff member.
        
        **Validation:**
        - Cannot reassign to the same staff member
        - New staff must be able to provide the service
        - New staff must be available at the booking time (no clashes)
        - A staff member must always be assigned (cannot remove without replacement)
        
        **Automatic behavior:**
        - Previous staff's schedule is freed at this time
        - New staff's schedule is blocked for this booking
        """,
        request=StaffReassignSerializer,
        examples=[
            OpenApiExample(
                'Reassign Staff',
                value={
                    'staff_member_id': 'b9743cc7-1364-4a32-a3b7-730a02365f00'
                },
                request_only=True
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Staff reassigned successfully",
                response={
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string', 'example': 'Staff reassigned from John to Jane'},
                        'previous_staff': {'type': 'string', 'example': 'John Doe'},
                        'new_staff': {'type': 'string', 'example': 'Jane Smith'},
                        'booking': {'type': 'object'}
                    }
                }
            ),
            400: OpenApiResponse(description="Bad Request - Same staff, staff unavailable, or cannot provide service"),
            403: OpenApiResponse(description="Forbidden - Not shop owner"),
            404: OpenApiResponse(description="Booking or staff not found")
        },
        tags=['Bookings - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient])
    def reassign_staff(self, request, pk=None):
        """Reassign a booking to a different staff member (shop owner only)."""
        booking = self.get_object()
        
        # Verify shop ownership
        if booking.shop.client.user != request.user:
            return Response(
                {'error': 'You do not own this shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Deal bookings don't have staff
        if booking.is_deal_booking:
            return Response(
                {'error': 'Deal bookings do not have staff assignments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cannot reassign completed/cancelled bookings
        if booking.status in ['completed', 'cancelled', 'no_show']:
            return Response(
                {'error': f'Cannot reassign staff for a booking with status: {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = StaffReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        staff_member_id = serializer.validated_data['staff_member_id']
        
        # Check if trying to reassign to the same staff
        if booking.staff_member and booking.staff_member.id == staff_member_id:
            return Response(
                {'error': 'This staff member is already assigned to this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get and validate staff member
        from apps.staff.models import StaffMember
        try:
            new_staff = StaffMember.objects.get(
                id=staff_member_id,
                shop=booking.shop,
                is_active=True
            )
        except StaffMember.DoesNotExist:
            return Response(
                {'error': 'Staff member not found or not active at this shop'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Deal bookings don't have staff - reject reassignment
        if booking.is_deal_booking:
            return Response(
                {'error': 'Deal bookings do not have assigned staff members and cannot be reassigned'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if staff can provide this service (only for service bookings)
        if booking.service and new_staff.services.exists() and not new_staff.services.filter(id=booking.service.id).exists():
            return Response(
                {
                    'error': 'This staff member cannot provide the booked service',
                    'staff_name': new_staff.name,
                    'service_name': booking.service.name,
                    'assigned_services': list(new_staff.services.values_list('name', flat=True))
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if new staff is available at this booking time (no clashes)
        from datetime import timedelta
        duration = booking.service.duration_minutes if booking.service else booking.duration_minutes
        booking_end = booking.booking_datetime + timedelta(minutes=duration)
        
        conflicting_booking = Booking.objects.filter(
            staff_member=new_staff,
            status__in=['pending', 'confirmed'],
            booking_datetime__lt=booking_end,
        ).exclude(id=booking.id)
        
        # Check for actual time overlap
        has_conflict = False
        conflict_details = None
        for existing_booking in conflicting_booking:
            existing_duration = (existing_booking.service.duration_minutes if existing_booking.service 
                               else existing_booking.duration_minutes)
            existing_end = existing_booking.booking_datetime + timedelta(minutes=existing_duration)
            if existing_booking.booking_datetime < booking_end and existing_end > booking.booking_datetime:
                has_conflict = True
                existing_item_name = (existing_booking.service.name if existing_booking.service 
                                     else (existing_booking.deal.name if existing_booking.deal else "Appointment"))
                conflict_details = {
                    'conflicting_booking_id': str(existing_booking.id),
                    'conflicting_time': existing_booking.booking_datetime.isoformat(),
                    'conflicting_item': existing_item_name
                }
                break
        
        if has_conflict:
            return Response(
                {
                    'error': f'{new_staff.name} already has a booking at this time',
                    'staff_name': new_staff.name,
                    'booking_time': booking.booking_datetime.isoformat(),
                    **conflict_details
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store old staff info before reassignment
        old_staff = booking.staff_member
        old_staff_name = old_staff.name if old_staff else 'Unassigned'
        
        # Update booking with new staff
        booking.staff_member = new_staff
        booking.save(update_fields=['staff_member'])
        
        return Response({
            'message': f'Staff reassigned from {old_staff_name} to {new_staff.name}',
            'previous_staff': old_staff_name,
            'new_staff': new_staff.name,
            'booking': BookingSerializer(booking).data
        })
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['my_bookings', 'dynamic_book', 'deal_slots', 'dynamic_book_deal']:
            return [IsCustomer()]
        elif self.action in ['shop_bookings', 'today_bookings', 'upcoming_bookings', 'confirm', 'complete', 'no_show', 'stats', 'reschedule', 'reassign_staff']:
            return [IsClient()]
        elif self.action == 'cancel':
            return [IsAuthenticated(), IsBookingOwner()]
        return super().get_permissions()
    
    # ============================================
    # Deal Booking Endpoints
    # ============================================
    
    @extend_schema(
        summary="Get deal availability slots",
        description="""
        Get available time slots for a deal booking.
        
        Deal slots are based on shop hours with capacity limits.
        Each slot shows `slots_left` (out of max_concurrent_deal_bookings).
        
        **Key differences from service availability:**
        - No staff required (just shop hours + capacity)
        - `slots_left` shows remaining capacity at each time
        """,
        parameters=[
            OpenApiParameter('deal_id', str, required=True, description='UUID of the deal'),
            OpenApiParameter('date', str, required=True, description='Date (YYYY-MM-DD)'),
        ],
        responses={
            200: DealAvailabilitySerializer,
            400: OpenApiResponse(description="Bad Request - Invalid deal or date"),
            404: OpenApiResponse(description="Deal not found")
        },
        tags=['Deals - Booking']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def deal_slots(self, request):
        """Get available slots for deal booking with capacity info."""
        from apps.services.models import Deal
        from apps.schedules.models import ShopSchedule
        from datetime import datetime, timedelta, time as dt_time
        import pytz
        
        deal_id = request.query_params.get('deal_id')
        date_str = request.query_params.get('date')
        
        if not deal_id or not date_str:
            return Response(
                {'error': 'deal_id and date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get deal
        try:
            deal = Deal.objects.select_related('shop').get(id=deal_id, is_active=True)
        except Deal.DoesNotExist:
            return Response(
                {'error': 'Deal not found or not active'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        shop = deal.shop
        max_concurrent = shop.max_concurrent_deal_bookings
        
        # Get shop's timezone
        try:
            shop_tz = pytz.timezone(shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        # Get schedule for this day
        day_name = target_date.strftime('%A').lower()
        try:
            schedule = ShopSchedule.objects.get(shop=shop, day_of_week=day_name)
        except ShopSchedule.DoesNotExist:
            return Response({
                'deal_id': str(deal.id),
                'deal_name': deal.name,
                'deal_duration_minutes': deal.duration_minutes,
                'date': date_str,
                'shop_open': None,
                'shop_close': None,
                'max_concurrent': max_concurrent,
                'slots': [],
                'message': 'Shop has no schedule for this day'
            })
        
        if not schedule.is_active or not schedule.start_time or not schedule.end_time:
            return Response({
                'deal_id': str(deal.id),
                'deal_name': deal.name,
                'deal_duration_minutes': deal.duration_minutes,
                'date': date_str,
                'shop_open': None,
                'shop_close': None,
                'max_concurrent': max_concurrent,
                'slots': [],
                'message': 'Shop is closed on this day'
            })
        
        # Generate slots based on shop hours and deal duration
        slot_duration = deal.duration_minutes
        slots = []
        
        # Get existing deal bookings for this date and shop
        existing_bookings = Booking.objects.filter(
            shop=shop,
            deal__isnull=False,
            booking_datetime__date=target_date,
            status__in=['pending', 'confirmed']
        )
        
        current_time = datetime.combine(target_date, schedule.start_time)
        end_time = datetime.combine(target_date, schedule.end_time)
        
        # Localize times to shop timezone
        current_time = shop_tz.localize(current_time)
        end_time = shop_tz.localize(end_time)
        
        now = timezone.now()
        buffer_time = now + timedelta(minutes=15)
        
        while current_time + timedelta(minutes=slot_duration) <= end_time:
            slot_end = current_time + timedelta(minutes=slot_duration)
            
            # Skip past slots
            if current_time < buffer_time:
                current_time = current_time + timedelta(minutes=30)  # 30-min slot intervals
                continue
            
            # Count overlapping bookings at this time
            overlapping = 0
            for booking in existing_bookings:
                booking_end = booking.booking_datetime + timedelta(minutes=booking.duration_minutes)
                # Check overlap
                if booking.booking_datetime < slot_end and booking_end > current_time:
                    overlapping += 1
            
            slots_left = max(0, max_concurrent - overlapping)
            
            slots.append({
                'start_time': current_time,
                'end_time': slot_end,
                'slots_left': slots_left,
                'is_available': slots_left > 0
            })
            
            current_time = current_time + timedelta(minutes=30)  # 30-min slot intervals
        
        return Response({
            'deal_id': str(deal.id),
            'deal_name': deal.name,
            'deal_duration_minutes': deal.duration_minutes,
            'date': date_str,
            'shop_open': schedule.start_time.strftime('%H:%M'),
            'shop_close': schedule.end_time.strftime('%H:%M'),
            'max_concurrent': max_concurrent,
            'slots': slots
        })
    
    @extend_schema(
        summary="Dynamic booking for deals",
        description="""
        Create a deal booking without staff assignment.
        
        Deal bookings are capacity-based (no staff required) and use the shop's
        max_concurrent_deal_bookings setting.
        
        The system will:
        1. Validate the slot is within shop hours
        2. Check capacity at the requested time
        3. Create the booking with 'pending' status
        4. Create a payment intent if Stripe Connect is enabled
        
        **Payment Flow:**
        - If shop owner has Stripe Connect enabled: Returns `client_secret` for payment
        - If shop doesn't have Stripe Connect: Booking is auto-confirmed
        - If advance payment is disabled: Booking is auto-confirmed
        
        **Response includes:**
        - Booking details (with deal information)
        - Payment object with either:
          - `client_secret` for Stripe.js (when payment required)
          - Confirmation message (when no payment required)
        """,
        request=DealBookingCreateSerializer,
        examples=[
            OpenApiExample(
                'Deal Booking Request',
                value={
                    'deal_id': 'f9e8d7c6b5a4-3210-fedc-ba98-76543210fedc',
                    'date': '2024-12-15',
                    'start_time': '14:00',
                    'duration_minutes': 90,
                    'notes': 'Birthday celebration'
                },
                request_only=True
            ),
            OpenApiExample(
                'Response with Payment Required',
                value={
                    'id': 'booking123',
                    'status': 'pending',
                    'deal': {'id': 'deal123', 'name': 'Spa Package'},
                    'booking_datetime': '2024-12-15T14:00:00Z',
                    'total_price': '120.00',
                    'payment': {
                        'required': True,
                        'client_secret': 'pi_xxx_secret_yyy',
                        'payment_intent_id': 'pi_xxx',
                        'amount': 12.0,
                        'amount_cents': 1200,
                        'currency': 'usd',
                        'message': 'Your slot is reserved for 15 minutes. Please complete payment within this time to confirm your booking.'
                    }
                },
                response_only=True
            )
        ],
        responses={
            201: BookingWithPaymentResponseSerializer,
            400: OpenApiResponse(description="No slots available or invalid data"),
            403: OpenApiResponse(description="Forbidden - Only customers can create bookings")
        },
        tags=['Bookings - Customer']
    )
    @action(detail=False, methods=['post'], permission_classes=[IsCustomer])
    def dynamic_book_deal(self, request):
        """Create a booking for a deal (no staff required)."""
        if request.user.role != 'customer':
            return Response(
                {'error': 'Only customers can create bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from apps.customers.models import Customer
        from datetime import timedelta
        import pytz
        
        customer, created = Customer.objects.get_or_create(user=request.user)
        
        serializer = DealBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        deal = serializer.validated_data['deal']
        booking_datetime = serializer.validated_data['booking_datetime']
        duration_minutes = serializer.validated_data['duration_minutes']
        
        shop = deal.shop
        max_concurrent = shop.max_concurrent_deal_bookings
        
        # Get shop's timezone
        try:
            shop_tz = pytz.timezone(shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        # Check capacity at this time
        slot_end = booking_datetime + timedelta(minutes=duration_minutes)
        
        existing_bookings = Booking.objects.filter(
            shop=shop,
            deal__isnull=False,
            status__in=['pending', 'confirmed'],
            booking_datetime__date=booking_datetime.date()
        )
        
        overlapping = 0
        for booking in existing_bookings:
            booking_end = booking.booking_datetime + timedelta(minutes=booking.duration_minutes)
            if booking.booking_datetime < slot_end and booking_end > booking_datetime:
                overlapping += 1
        
        if overlapping >= max_concurrent:
            return Response(
                {
                    'error': 'No slots available at this time. Maximum capacity reached.',
                    'slots_left': 0,
                    'max_concurrent': max_concurrent
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create booking (no staff, no time_slot)
        booking = Booking.objects.create(
            customer=customer,
            shop=shop,
            service=None,  # No service for deal booking
            deal=deal,
            time_slot=None,
            staff_member=None,  # No staff for deal booking
            booking_datetime=booking_datetime,
            duration_minutes=duration_minutes,
            total_price=deal.price,
            notes=serializer.validated_data.get('notes', ''),
            status='pending'
        )
        
        # Attempt to create advance payment
        payment_result = booking_payment_service.create_advance_payment(booking)
        
        # Build response
        response_data = BookingSerializer(booking).data
        
        if payment_result.get('payment_required'):
            # Payment is required - return client_secret for Stripe.js
            response_data['payment'] = {
                'required': True,
                'client_secret': payment_result['client_secret'],
                'payment_intent_id': payment_result['payment_intent_id'],
                'amount': float(payment_result['amount']),
                'amount_cents': payment_result['amount_cents'],
                'currency': payment_result['currency'],
                'message': 'Your slot is reserved for 15 minutes. Please complete payment within this time to confirm your booking.'
            }
            
            # Schedule auto-cancellation after 15 minutes if payment not completed
            from apps.bookings.tasks import cancel_unpaid_booking
            cancel_unpaid_booking.apply_async(
                args=[str(booking.id)],
                countdown=15 * 60  # 15 minutes in seconds
            )
        else:
            # Payment not required - booking auto-confirmed
            response_data['payment'] = {
                'required': False,
                'message': payment_result.get('message', 'No advance payment required')
            }
        
        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )

