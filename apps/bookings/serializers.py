"""
Booking serializers
"""
from rest_framework import serializers
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


class BookingListSerializer(serializers.ModelSerializer):
    """Simplified booking serializer for lists"""
    customer_name = serializers.CharField(source='customer.user.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    staff_member_name = serializers.CharField(source='staff_member.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer_name', 'shop_name', 'service_name',
            'staff_member_name', 'booking_datetime', 'status',
            'total_price', 'created_at'
        ]


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
