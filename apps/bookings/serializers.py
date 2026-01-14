"""
Booking serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import Booking
from django.utils import timezone


class BookingSerializer(serializers.ModelSerializer):
    """Detailed booking serializer for output - supports both service and deal bookings"""
    customer_name = serializers.CharField(source='customer.user.full_name', read_only=True)
    customer_email = serializers.EmailField(source='customer.user.email', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    # Service fields (null for deal bookings)
    service_name = serializers.CharField(source='service.name', read_only=True, allow_null=True)
    service_price = serializers.DecimalField(
        source='service.price',
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )
    # Deal fields (null for service bookings)
    deal_name = serializers.CharField(source='deal.name', read_only=True, allow_null=True)
    deal_price = serializers.DecimalField(
        source='deal.price',
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )
    deal_items = serializers.JSONField(source='deal.included_items', read_only=True, default=list)
    # Common fields
    staff_member_name = serializers.CharField(source='staff_member.name', read_only=True, allow_null=True)
    is_deal_booking = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer', 'customer_name', 'customer_email',
            'shop', 'shop_name', 
            # Service booking fields
            'service', 'service_name', 'service_price',
            # Deal booking fields
            'deal', 'deal_name', 'deal_price', 'deal_items',
            # Common fields
            'time_slot', 'staff_member', 'staff_member_name',
            'booking_datetime', 'duration_minutes', 'status', 
            'total_price', 'notes', 'is_deal_booking',
            'cancellation_reason', 'cancelled_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'customer', 'shop', 'total_price',
            'cancelled_at', 'created_at', 'updated_at'
        ]


class BookingCreateSerializer(serializers.Serializer):
    """Input serializer for creating bookings"""
    service_id = serializers.UUIDField()
    time_slot_id = serializers.UUIDField()
    staff_member_id = serializers.UUIDField(required=False, allow_null=True, help_text="Optional: Select a specific staff member")
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate(self, data):
        from apps.services.models import Service
        from apps.schedules.models import TimeSlot
        from apps.staff.models import StaffMember
        
        # Validate service exists
        try:
            service = Service.objects.get(id=data['service_id'], is_active=True)
        except Service.DoesNotExist:
            raise serializers.ValidationError("Service not found or not available")
        
        # Validate time slot
        try:
            time_slot = TimeSlot.objects.get(id=data['time_slot_id'])
        except TimeSlot.DoesNotExist:
            raise serializers.ValidationError("Time slot not found")
        
        if time_slot.status != 'available':
            raise serializers.ValidationError("This time slot is not available")
        
        if time_slot.start_datetime < timezone.now():
            raise serializers.ValidationError("Cannot book past time slots")
        
        # Verify time slot belongs to the same shop as service
        if time_slot.schedule.shop != service.shop:
            raise serializers.ValidationError("Time slot and service must be from the same shop")
        
        # Validate staff member if provided
        if data.get('staff_member_id'):
            try:
                staff_member = StaffMember.objects.get(
                    id=data['staff_member_id'],
                    shop=service.shop,
                    is_active=True
                )
                # Verify staff can provide this service
                if not staff_member.services.filter(id=service.id).exists():
                    raise serializers.ValidationError(
                        "Selected staff member cannot provide this service"
                    )
            except StaffMember.DoesNotExist:
                raise serializers.ValidationError(
                    "Staff member not found or not available at this shop"
                )
        
        return data


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Pending Booking (Payable)',
            value={
                'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                'customer_name': 'John Doe',
                'shop_name': 'Elegant Salon',
                'service_name': 'Haircut & Style',
                'deal_name': None,
                'item_name': 'Haircut & Style',
                'is_deal_booking': False,
                'staff_member_name': 'Sarah Johnson',
                'booking_datetime': '2026-01-15T14:00:00Z',
                'duration_minutes': 45,
                'status': 'pending',
                'payment_status': 'pending',
                'can_pay': True,
                'client_secret': 'pi_3Abc123XYz_secret_def456',
                'payment_expires_at': '2026-01-14T12:45:00Z',
                'time_remaining_seconds': 845,
                'payment_amount': 5.00,
                'total_price': '50.00',
                'created_at': '2026-01-14T12:30:00Z'
            },
            response_only=True
        ),
        OpenApiExample(
            'Confirmed Booking',
            value={
                'id': 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
                'customer_name': 'Jane Smith',
                'shop_name': 'Elegant Salon',
                'service_name': None,
                'deal_name': 'Spa Package',
                'item_name': 'Spa Package',
                'is_deal_booking': True,
                'staff_member_name': None,
                'booking_datetime': '2026-01-16T10:00:00Z',
                'duration_minutes': 90,
                'status': 'confirmed',
                'payment_status': 'paid',
                'can_pay': False,
                'client_secret': None,
                'payment_expires_at': None,
                'time_remaining_seconds': None,
                'payment_amount': None,
                'total_price': '120.00',
                'created_at': '2026-01-13T09:00:00Z'
            },
            response_only=True
        )
    ]
)
class BookingListSerializer(serializers.ModelSerializer):
    """Simplified booking serializer for lists - supports both service and deal bookings"""
    customer_name = serializers.CharField(source='customer.user.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    # Service booking
    service_name = serializers.CharField(source='service.name', read_only=True, allow_null=True)
    # Deal booking
    deal_name = serializers.CharField(source='deal.name', read_only=True, allow_null=True)
    is_deal_booking = serializers.BooleanField(read_only=True)
    # Common
    staff_member_name = serializers.CharField(source='staff_member.name', read_only=True, allow_null=True)
    
    # Computed field for display name (service or deal)
    item_name = serializers.SerializerMethodField()
    
    # Payment fields
    payment_status = serializers.CharField(read_only=True)
    can_pay = serializers.SerializerMethodField(help_text="True if booking can be paid (pending and within 15-min window)")
    
    # Payment info for Stripe.js (only present when can_pay is True)
    client_secret = serializers.SerializerMethodField(help_text="Stripe client_secret for payment (null if not payable)")
    payment_expires_at = serializers.SerializerMethodField(help_text="When payment window expires")
    time_remaining_seconds = serializers.SerializerMethodField(help_text="Seconds remaining to pay")
    payment_amount = serializers.SerializerMethodField(help_text="Advance payment amount")
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer_name', 'shop_name', 
            'service_name', 'deal_name', 'item_name', 'is_deal_booking',
            'staff_member_name', 'booking_datetime', 'duration_minutes',
            'status', 'payment_status', 'can_pay', 
            'client_secret', 'payment_expires_at', 'time_remaining_seconds', 'payment_amount',
            'total_price', 'created_at'
        ]
    
    def get_item_name(self, obj):
        """Return the display name (service name or deal name)"""
        if obj.service:
            return obj.service.name
        elif obj.deal:
            return obj.deal.name
        return 'Unknown'
    
    def get_can_pay(self, obj):
        """
        Check if booking can still be paid.
        Returns True only if:
        - Status is 'pending'
        - Payment status is 'pending'
        - Payment window hasn't expired (within 15 mins of creation)
        """
        if obj.status != 'pending' or obj.payment_status != 'pending':
            return False
        try:
            payment = obj.advance_payment
            if payment and payment.payment_expires_at:
                return payment.payment_expires_at > timezone.now()
        except Exception:
            pass
        return False
    
    def get_client_secret(self, obj):
        """Return client_secret only if booking can be paid."""
        if not self.get_can_pay(obj):
            return None
        try:
            payment = obj.advance_payment
            return payment.metadata.get('client_secret')
        except Exception:
            return None
    
    def get_payment_expires_at(self, obj):
        """Return payment expiry time if applicable."""
        if obj.status != 'pending' or obj.payment_status != 'pending':
            return None
        try:
            payment = obj.advance_payment
            if payment and payment.payment_expires_at:
                return payment.payment_expires_at
        except Exception:
            pass
        return None
    
    def get_time_remaining_seconds(self, obj):
        """Return seconds remaining in payment window."""
        expires_at = self.get_payment_expires_at(obj)
        if expires_at:
            remaining = (expires_at - timezone.now()).total_seconds()
            return max(0, int(remaining))
        return None
    
    def get_payment_amount(self, obj):
        """Return advance payment amount if applicable."""
        if obj.status != 'pending' or obj.payment_status != 'pending':
            return None
        try:
            payment = obj.advance_payment
            return float(payment.amount) if payment else None
        except Exception:
            return None


class BookingUpdateStatusSerializer(serializers.Serializer):
    """Input serializer for updating booking status"""
    status = serializers.ChoiceField(
        choices=['confirmed', 'completed', 'cancelled', 'no_show']
    )
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )
    
    def validate(self, data):
        if data['status'] == 'cancelled' and not data.get('cancellation_reason'):
            raise serializers.ValidationError(
                "Cancellation reason is required when cancelling a booking"
            )
        return data


class BookingRescheduleSerializer(serializers.Serializer):
    """Input serializer for rescheduling bookings"""
    new_time_slot_id = serializers.UUIDField()
    
    def validate_new_time_slot_id(self, value):
        from apps.schedules.models import TimeSlot
        
        try:
            time_slot = TimeSlot.objects.get(id=value)
        except TimeSlot.DoesNotExist:
            raise serializers.ValidationError("Time slot not found")
        
        if time_slot.status != 'available':
            raise serializers.ValidationError("This time slot is not available")
        
        if time_slot.start_datetime < timezone.now():
            raise serializers.ValidationError("Cannot reschedule to a past time slot")
        
        return value


class BookingStatsSerializer(serializers.Serializer):
    """Output serializer for booking statistics"""
    total_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)


# ============================================
# Owner Booking Management Serializers
# ============================================

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Reschedule to next week',
            value={
                'date': '2024-12-20',
                'start_time': '14:00'
            },
            request_only=True,
            description='Reschedule booking to December 20th at 2 PM'
        ),
        OpenApiExample(
            'Same day reschedule',
            value={
                'date': '2024-12-16',
                'start_time': '10:30'
            },
            request_only=True,
            description='Reschedule to a different time on the same day'
        )
    ]
)
class OwnerRescheduleSerializer(serializers.Serializer):
    """
    Serializer for shop owner to reschedule a booking.
    
    Uses dynamic availability to validate the new slot.
    The new slot must be available (shop open, staff available).
    """
    date = serializers.DateField(
        help_text="New date for the booking (YYYY-MM-DD)"
    )
    start_time = serializers.TimeField(
        help_text="New start time for the booking (HH:MM)"
    )
    
    def validate_date(self, value):
        """Ensure date is not in the past."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Date cannot be in the past")
        return value


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Reassign to specific staff',
            value={
                'staff_member_id': 'b9743cc7-1364-4a32-a3b7-730a02365f00'
            },
            request_only=True,
            description='Reassign booking to a different staff member'
        )
    ]
)
class StaffReassignSerializer(serializers.Serializer):
    """
    Serializer for shop owner to reassign staff for a booking.
    
    Validates that:
    - Cannot reassign to the same staff member
    - Staff member exists and is active
    - Staff member belongs to the same shop
    - Staff member can provide the service
    - Staff member is available at the booking time (no clashes)
    """
    staff_member_id = serializers.UUIDField(
        help_text="UUID of the new staff member to assign. Cannot be the same as current staff."
    )


class StaffReassignResponseSerializer(serializers.Serializer):
    """Response serializer for staff reassignment."""
    message = serializers.CharField()
    previous_staff = serializers.CharField()
    new_staff = serializers.CharField()
    booking = BookingSerializer()


class OwnerRescheduleResponseSerializer(serializers.Serializer):
    """Response serializer for owner reschedule."""
    message = serializers.CharField(required=False)
    booking = BookingSerializer()


# ============================================
# Dynamic Booking Serializers (No TimeSlot Required)
# ============================================

class DynamicBookingCreateSerializer(serializers.Serializer):
    """
    Input serializer for creating bookings without pre-created TimeSlots.
    
    Uses dynamic availability to validate and create bookings directly
    from a service_id, date, and start_time.
    """
    service_id = serializers.UUIDField(
        help_text="UUID of the service to book"
    )
    date = serializers.DateField(
        help_text="Date of the booking (YYYY-MM-DD)"
    )
    start_time = serializers.TimeField(
        help_text="Start time for the booking (HH:MM)"
    )
    staff_member_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional: Select a specific staff member"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional notes for the booking"
    )
    
    def validate_date(self, value):
        """Ensure date is not in the past."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Date cannot be in the past")
        return value
    
    def validate_service_id(self, value):
        """Validate service exists and is active."""
        from apps.services.models import Service
        try:
            Service.objects.get(id=value, is_active=True)
        except Service.DoesNotExist:
            raise serializers.ValidationError("Service not found or not active")
        return value
    
    def validate(self, data):
        from apps.services.models import Service
        from apps.staff.models import StaffMember
        from datetime import datetime, timedelta
        import pytz
        
        service = Service.objects.select_related('shop').get(id=data['service_id'])
        
        # Get shop's timezone
        try:
            shop_tz = pytz.timezone(service.shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        # Create datetime from date and time, localized to shop's timezone
        # The date and time from request are interpreted as shop's local time
        naive_datetime = datetime.combine(data['date'], data['start_time'])
        booking_datetime = shop_tz.localize(naive_datetime)
        
        # Check if booking time is in the past (compare in UTC)
        buffer_time = timezone.now() + timedelta(minutes=15)
        if booking_datetime < buffer_time:
            raise serializers.ValidationError(
                "Booking time must be at least 15 minutes from now"
            )
        
        # Validate staff member if provided
        if data.get('staff_member_id'):
            try:
                staff_member = StaffMember.objects.get(
                    id=data['staff_member_id'],
                    shop=service.shop,
                    is_active=True
                )
                # Verify staff can provide this service (if they have service assignments)
                staff_services = staff_member.services.all()
                if staff_services.exists() and not staff_services.filter(id=service.id).exists():
                    raise serializers.ValidationError(
                        "Selected staff member cannot provide this service"
                    )
            except StaffMember.DoesNotExist:
                raise serializers.ValidationError(
                    "Staff member not found or not available at this shop"
                )
        
        data['booking_datetime'] = booking_datetime
        data['service'] = service
        return data


# ============================================
# Deal Booking Serializers
# ============================================

class DealSlotSerializer(serializers.Serializer):
    """Output serializer for deal availability slots with capacity info."""
    start_time = serializers.DateTimeField(help_text="Slot start time")
    end_time = serializers.DateTimeField(help_text="Slot end time")
    slots_left = serializers.IntegerField(help_text="Number of available slots (out of max concurrent)")
    is_available = serializers.BooleanField(help_text="True if at least 1 slot is available")


class DealAvailabilitySerializer(serializers.Serializer):
    """Output serializer for deal availability check."""
    deal_id = serializers.UUIDField()
    deal_name = serializers.CharField()
    deal_duration_minutes = serializers.IntegerField()
    date = serializers.DateField()
    shop_open = serializers.TimeField(allow_null=True)
    shop_close = serializers.TimeField(allow_null=True)
    max_concurrent = serializers.IntegerField(help_text="Max concurrent deal bookings for shop")
    slots = DealSlotSerializer(many=True)


class DealBookingCreateSerializer(serializers.Serializer):
    """
    Input serializer for creating deal bookings.
    
    Deal bookings don't require staff - just based on shop hours and capacity.
    """
    deal_id = serializers.UUIDField(
        help_text="UUID of the deal to book"
    )
    date = serializers.DateField(
        help_text="Date of the booking (YYYY-MM-DD)"
    )
    start_time = serializers.TimeField(
        help_text="Start time for the booking (HH:MM)"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional notes for the booking"
    )
    
    def validate_date(self, value):
        """Ensure date is not in the past."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Date cannot be in the past")
        return value
    
    def validate_deal_id(self, value):
        """Validate deal exists and is active."""
        from apps.services.models import Deal
        try:
            Deal.objects.get(id=value, is_active=True)
        except Deal.DoesNotExist:
            raise serializers.ValidationError("Deal not found or not active")
        return value
    
    def validate(self, data):
        from apps.services.models import Deal
        from datetime import datetime, timedelta
        import pytz
        
        deal = Deal.objects.select_related('shop').get(id=data['deal_id'])
        
        # Get shop's timezone
        try:
            shop_tz = pytz.timezone(deal.shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            shop_tz = pytz.UTC
        
        # Create datetime from date and time, localized to shop's timezone
        naive_datetime = datetime.combine(data['date'], data['start_time'])
        booking_datetime = shop_tz.localize(naive_datetime)
        
        # Check if booking time is in the past
        buffer_time = timezone.now() + timedelta(minutes=15)
        if booking_datetime < buffer_time:
            raise serializers.ValidationError(
                "Booking time must be at least 15 minutes from now"
            )
        
        data['booking_datetime'] = booking_datetime
        data['deal'] = deal
        data['duration_minutes'] = deal.duration_minutes
        return data


# ============================================
# Payment Response Serializers
# ============================================

class PaymentInfoSerializer(serializers.Serializer):
    """
    Payment information returned with booking creation.
    
    Included in the booking response to indicate whether payment is required
    and provide the client_secret for Stripe.js integration.
    """
    required = serializers.BooleanField(
        help_text="Whether advance payment is required for this booking"
    )
    message = serializers.CharField(
        help_text="Message about payment status or requirements"
    )
    # Fields below are only present when payment is required
    client_secret = serializers.CharField(
        required=False,
        help_text="Stripe PaymentIntent client secret for frontend payment processing"
    )
    payment_intent_id = serializers.CharField(
        required=False,
        help_text="Stripe PaymentIntent ID"
    )
    amount = serializers.FloatField(
        required=False,
        help_text="Advance payment amount in dollars"
    )
    amount_cents = serializers.IntegerField(
        required=False,
        help_text="Advance payment amount in cents"
    )
    currency = serializers.CharField(
        required=False,
        help_text="Payment currency (e.g., 'usd')"
    )


class PaymentErrorSerializer(serializers.Serializer):
    """Error response serializer for payment-info endpoint."""
    error = serializers.CharField(help_text="Error message")
    expired_at = serializers.DateTimeField(
        required=False,
        help_text="When payment window expired (if applicable)"
    )
    message = serializers.CharField(
        required=False,
        help_text="Additional user-friendly message"
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Payment Info Response',
            value={
                'booking_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                'client_secret': 'pi_3Abc123XYz_secret_def456',
                'payment_intent_id': 'pi_3Abc123XYz',
                'amount': 5.00,
                'currency': 'usd',
                'expires_at': '2026-01-14T12:45:00Z',
                'time_remaining_seconds': 845,
                'can_pay': True
            },
            response_only=True
        )
    ]
)
class PaymentRetrievalSerializer(serializers.Serializer):
    """
    Response serializer for retrieving payment info for an existing booking.
    Used by GET /bookings/{id}/payment-info/ endpoint.
    """
    booking_id = serializers.UUIDField(help_text="Booking ID")
    client_secret = serializers.CharField(
        help_text="Stripe PaymentIntent client secret for payment processing"
    )
    payment_intent_id = serializers.CharField(
        help_text="Stripe PaymentIntent ID"
    )
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Advance payment amount"
    )
    currency = serializers.CharField(help_text="Payment currency")
    expires_at = serializers.DateTimeField(
        help_text="When the payment window expires"
    )
    time_remaining_seconds = serializers.IntegerField(
        help_text="Seconds remaining in payment window"
    )
    can_pay = serializers.BooleanField(
        help_text="True if payment window is still open"
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Booking with Payment Required',
            value={
                'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                'customer': 'cust-uuid',
                'customer_name': 'John Doe',
                'customer_email': 'john@example.com',
                'shop': 'shop-uuid',
                'shop_name': 'Elegant Salon',
                'service': 'service-uuid',
                'service_name': 'Haircut & Style',
                'service_price': '50.00',
                'deal': None,
                'deal_name': None,
                'staff_member': 'staff-uuid',
                'staff_member_name': 'Jane Smith',
                'booking_datetime': '2024-12-10T10:00:00Z',
                'duration_minutes': 60,
                'status': 'pending',
                'payment_status': 'pending',
                'total_price': '50.00',
                'notes': 'Please call when you arrive',
                'is_deal_booking': False,
                'created_at': '2024-12-01T14:30:00Z',
                'payment': {
                    'required': True,
                    'client_secret': 'pi_3Abc123XYz_secret_def456',
                    'payment_intent_id': 'pi_3Abc123XYz',
                    'amount': 5.0,
                    'amount_cents': 500,
                    'currency': 'usd',
                    'message': 'Please complete payment to confirm booking'
                }
            },
            response_only=True
        ),
        OpenApiExample(
            'Booking without Payment Required',
            value={
                'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                'customer': 'cust-uuid',
                'customer_name': 'John Doe',
                'customer_email': 'john@example.com',
                'shop': 'shop-uuid',
                'shop_name': 'Elegant Salon',
                'service': 'service-uuid',
                'service_name': 'Haircut & Style',
                'service_price': '50.00',
                'deal': None,
                'deal_name': None,
                'staff_member': 'staff-uuid',
                'staff_member_name': 'Jane Smith',
                'booking_datetime': '2024-12-10T10:00:00Z',
                'duration_minutes': 60,
                'status': 'confirmed',
                'payment_status': 'not_required',
                'total_price': '50.00',
                'notes': 'Please call when you arrive',
                'is_deal_booking': False,
                'created_at': '2024-12-01T14:30:00Z',
                'payment': {
                    'required': False,
                    'message': 'Shop payment setup incomplete - booking created without deposit'
                }
            },
            response_only=True
        ),
        OpenApiExample(
            'Deal Booking with Payment',
            value={
                'id': 'deal-booking-uuid',
                'customer': 'cust-uuid',
                'customer_name': 'John Doe',
                'shop': 'shop-uuid',
                'shop_name': 'Spa Paradise',
                'service': None,
                'service_name': None,
                'deal': 'deal-uuid',
                'deal_name': 'Spa Package Deluxe',
                'deal_price': '120.00',
                'deal_items': ['Full body massage', 'Facial treatment', 'Aromatherapy'],
                'staff_member': None,
                'staff_member_name': None,
                'booking_datetime': '2024-12-15T14:00:00Z',
                'duration_minutes': 90,
                'status': 'pending',
                'payment_status': 'pending',
                'total_price': '120.00',
                'notes': 'Birthday celebration',
                'is_deal_booking': True,
                'created_at': '2024-12-01T15:00:00Z',
                'payment': {
                    'required': True,
                    'client_secret': 'pi_7Def456ABC_secret_ghi789',
                    'payment_intent_id': 'pi_7Def456ABC',
                    'amount': 12.0,
                    'amount_cents': 1200,
                    'currency': 'usd',
                    'message': 'Please complete payment to confirm booking'
                }
            },
            response_only=True
        )
    ]
)
class BookingWithPaymentResponseSerializer(serializers.Serializer):
    """
    Complete booking response including payment information.
    
    This serializer documents the full response structure returned by
    booking creation endpoints when they include payment details.
    """
    # Booking fields (from BookingSerializer)
    id = serializers.UUIDField(read_only=True)
    customer = serializers.UUIDField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_email = serializers.EmailField(read_only=True)
    shop = serializers.UUIDField(read_only=True)
    shop_name = serializers.CharField(read_only=True)
    service = serializers.UUIDField(read_only=True, allow_null=True)
    service_name = serializers.CharField(read_only=True, allow_null=True)
    service_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    deal = serializers.UUIDField(read_only=True, allow_null=True)
    deal_name = serializers.CharField(read_only=True, allow_null=True)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    deal_items = serializers.JSONField(read_only=True, default=list)
    staff_member = serializers.UUIDField(read_only=True, allow_null=True)
    staff_member_name = serializers.CharField(read_only=True, allow_null=True)
    booking_datetime = serializers.DateTimeField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    payment_status = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    notes = serializers.CharField(read_only=True)
    is_deal_booking = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Payment information (added by view)
    payment = PaymentInfoSerializer(
        help_text="Payment information for this booking"
    )
