"""
Schedule and TimeSlot serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ShopSchedule, TimeSlot
from datetime import datetime
from django.utils import timezone


class ShopScheduleSerializer(serializers.ModelSerializer):
    """Serializer for ShopSchedule model"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    
    class Meta:
        model = ShopSchedule
        fields = [
            'id', 'shop', 'shop_name', 'day_of_week',
            'start_time', 'end_time', 'slot_duration_minutes',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']
    
    def validate(self, data):
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("End time must be after start time")
        return data


class ShopScheduleCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating shop schedules"""
    
    class Meta:
        model = ShopSchedule
        fields = ['day_of_week', 'start_time', 'end_time', 'slot_duration_minutes', 'is_active']
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class TimeSlotSerializer(serializers.ModelSerializer):
    """Serializer for TimeSlot model"""
    shop_name = serializers.CharField(source='schedule.shop.name', read_only=True)
    
    @extend_schema_field(serializers.BooleanField)
    def get_is_available(self, obj):
        return obj.status == 'available' and obj.start_datetime > timezone.now()
    
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeSlot
        fields = [
            'id', 'schedule', 'shop_name', 'start_datetime',
            'end_datetime', 'status', 'is_available',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'schedule', 'created_at', 'updated_at']


class TimeSlotGenerateSerializer(serializers.Serializer):
    """Input serializer for generating time slots"""
    shop_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError("Start date cannot be in the past")
        if (data['end_date'] - data['start_date']).days > 90:
            raise serializers.ValidationError("Cannot generate slots for more than 90 days")
        return data


class TimeSlotGenerateResponseSerializer(serializers.Serializer):
    """Output serializer for time slot generation response"""
    message = serializers.CharField()
    slots_created = serializers.IntegerField()
    date_range = serializers.DictField()


class AvailabilityCheckSerializer(serializers.Serializer):
    """Input serializer for checking availability"""
    shop_id = serializers.IntegerField()
    service_id = serializers.IntegerField(required=False)
    date = serializers.DateField()


class AvailabilityResponseSerializer(serializers.Serializer):
    """Output serializer for availability response"""
    date = serializers.DateField()
    available_slots = TimeSlotSerializer(many=True)
    total_slots = serializers.IntegerField()


class TimeSlotBlockSerializer(serializers.Serializer):
    """Input serializer for blocking/unblocking time slots"""
    reason = serializers.CharField(required=False, allow_blank=True)
