"""
Booking serializers
"""
from rest_framework import serializers
from .models import Booking
from django.utils import timezone


class BookingSerializer(serializers.ModelSerializer):
    """Detailed booking serializer for output"""
    customer_name = serializers.CharField(source='customer.user.full_name', read_only=True)
    customer_email = serializers.EmailField(source='customer.user.email', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_price = serializers.DecimalField(
        source='service.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    service_duration = serializers.IntegerField(
        source='service.duration_minutes',
        read_only=True
    )
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer', 'customer_name', 'customer_email',
            'shop', 'shop_name', 'service', 'service_name',
            'service_price', 'service_duration', 'time_slot',
            'booking_datetime', 'status', 'total_price', 'notes',
            'cancellation_reason', 'cancelled_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'customer', 'shop', 'total_price',
            'cancelled_at', 'created_at', 'updated_at'
        ]


class BookingCreateSerializer(serializers.Serializer):
    """Input serializer for creating bookings"""
    service_id = serializers.IntegerField()
    time_slot_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate(self, data):
        from apps.services.models import Service
        from apps.schedules.models import TimeSlot
        
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
        
        return data


class BookingListSerializer(serializers.ModelSerializer):
    """Simplified booking serializer for lists"""
    customer_name = serializers.CharField(source='customer.user.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'customer_name', 'shop_name', 'service_name',
            'booking_datetime', 'status', 'total_price', 'created_at'
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
    new_time_slot_id = serializers.IntegerField()
    
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
