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
    
    @extend_schema_field(serializers.DateField)
    def get_next_occurrence(self, obj):
        """Calculate the next date this schedule will be active"""
        from datetime import datetime, timedelta
        
        days_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        today = datetime.now().date()
        target_day_num = days_map[obj.day_of_week.lower()]
        current_day_num = today.weekday()
        
        days_ahead = target_day_num - current_day_num
        if days_ahead <= 0:  # Target day already happened this week or is today
            days_ahead += 7
            
        next_date = today + timedelta(days=days_ahead)
        return next_date.isoformat()
    
    next_occurrence = serializers.SerializerMethodField()
    
    class Meta:
        model = ShopSchedule
        fields = [
            'id', 'shop', 'shop_name', 'day_of_week',
            'start_time', 'end_time', 'slot_duration_minutes',
            'is_active', 'next_occurrence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']
    
    def validate(self, data):
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("End time must be after start time")
        return data


class ShopScheduleCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating shop schedules"""
    shop_id = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = ShopSchedule
        fields = ['shop_id', 'day_of_week', 'start_time', 'end_time', 'is_active']
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class TimeSlotSerializer(serializers.ModelSerializer):
    """Serializer for TimeSlot model"""
    shop_name = serializers.CharField(source='schedule.shop.name', read_only=True)
    staff_member_name = serializers.CharField(source='staff_member.name', read_only=True, allow_null=True)
    
    @extend_schema_field(serializers.BooleanField)
    def get_is_available(self, obj):
        return obj.status == 'available' and obj.start_datetime > timezone.now()
    
    @extend_schema_field(serializers.IntegerField)
    def get_duration_minutes(self, obj):
        """Calculate duration in minutes from start and end datetime"""
        delta = obj.end_datetime - obj.start_datetime
        return int(delta.total_seconds() / 60)
    
    is_available = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeSlot
        fields = [
            'id', 'schedule', 'shop_name', 'start_datetime',
            'end_datetime', 'duration_minutes', 'status', 'staff_member',
            'staff_member_name', 'is_available',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'schedule', 'created_at', 'updated_at']


class TimeSlotGenerateSerializer(serializers.Serializer):
    """Input serializer for generating time slots"""
    shop_id = serializers.UUIDField()
    start_date = serializers.DateField()

    day_name = serializers.ChoiceField(choices=[
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ])
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    staff_member_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional: Assign a specific staff member to this time slot"
    )
    
    def validate(self, data):
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError("Start date cannot be in the past")
        
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
                
        return data


class TimeSlotGenerateResponseSerializer(serializers.Serializer):
    """Output serializer for time slot generation response"""
    message = serializers.CharField()
    slots_created = serializers.IntegerField()
    date_range = serializers.DictField()


class AvailabilityCheckSerializer(serializers.Serializer):
    """Input serializer for checking availability"""
    shop_id = serializers.UUIDField()
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
