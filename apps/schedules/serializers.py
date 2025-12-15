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


class BulkScheduleCreateSerializer(serializers.Serializer):
    """
    Serializer for creating schedules for multiple days at once.
    
    Set shop hours for selected days (e.g., Monday, Wednesday, Friday).
    Days don't need to be sequential - select any days you want.
    Slot duration is determined by service duration, not fixed intervals.
    """
    shop_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the shop"
    )
    days = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                ('monday', 'Monday'),
                ('tuesday', 'Tuesday'),
                ('wednesday', 'Wednesday'),
                ('thursday', 'Thursday'),
                ('friday', 'Friday'),
                ('saturday', 'Saturday'),
                ('sunday', 'Sunday'),
            ]
        ),
        min_length=1,
        help_text="List of days to set schedule for (e.g., ['monday', 'wednesday', 'friday'])"
    )
    start_time = serializers.TimeField(
        help_text="Opening time (e.g., '09:00')"
    )
    end_time = serializers.TimeField(
        help_text="Closing time (e.g., '18:00')"
    )
    
    class Meta:
        # OpenAPI example schema
        examples = [
            {
                "name": "Weekday Schedule",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    "start_time": "09:00",
                    "end_time": "18:00"
                }
            },
            {
                "name": "Weekend Only",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "days": ["saturday", "sunday"],
                    "start_time": "10:00",
                    "end_time": "16:00"
                }
            },
            {
                "name": "Custom Days",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "days": ["monday", "wednesday", "friday"],
                    "start_time": "08:00",
                    "end_time": "20:00"
                }
            }
        ]
    
    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Remove duplicates and validate days
        data['days'] = list(set(data['days']))
        
        return data
    
    def get_days(self):
        """Get the list of days from validated data."""
        return self.validated_data['days']


class BulkScheduleResponseSerializer(serializers.Serializer):
    """Response serializer for bulk schedule creation."""
    message = serializers.CharField()
    schedules_created = serializers.IntegerField()
    schedules_updated = serializers.IntegerField()
    days = serializers.ListField(child=serializers.CharField())
    shop_hours = serializers.DictField(
        help_text="Shop opening/closing times applied"
    )


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
    service_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional: Service this slot is for (validates staff assignment)"
    )
    
    def validate(self, data):
        if data['start_date'] < datetime.now().date():
            raise serializers.ValidationError("Start date cannot be in the past")
        
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        # If both service and staff are specified, validate the relationship
        if data.get('service_id') and data.get('staff_member_id'):
            from apps.staff.models import StaffService
            
            is_assigned = StaffService.objects.filter(
                service_id=data['service_id'],
                staff_member_id=data['staff_member_id']
            ).exists()
            
            if not is_assigned:
                raise serializers.ValidationError({
                    'staff_member_id': 'This staff member is not assigned to the specified service'
                })
                
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


# ============================================
# Dynamic Availability Serializers
# ============================================

class DynamicAvailabilityRequestSerializer(serializers.Serializer):
    """
    Input serializer for dynamic availability calculator.
    
    Computes available time slots on-the-fly based on:
    - Shop schedule (open/close times)
    - Service duration (slots are generated based on service duration)
    - Staff availability (booking conflicts)
    - Service buffer_minutes (minimum time before booking)
    """
    service_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the service to check availability for"
    )
    date = serializers.DateField(
        required=True,
        help_text="Target date to check availability (YYYY-MM-DD format)"
    )
    buffer_minutes_override = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=120,
        help_text="Optional override for minimum minutes from now. If not provided, uses service.buffer_minutes."
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


class AvailableStaffSerializer(serializers.Serializer):
    """Staff member details for availability response."""
    id = serializers.UUIDField(help_text="Staff member UUID")
    name = serializers.CharField(help_text="Staff member name")
    email = serializers.EmailField(required=False, allow_null=True, help_text="Staff member email")
    phone = serializers.CharField(required=False, allow_null=True, help_text="Staff member phone")
    profile_image_url = serializers.URLField(required=False, allow_null=True, allow_blank=True, help_text="Staff profile image URL")
    is_primary = serializers.BooleanField(required=False, help_text="Is primary staff for this service")


class AvailableSlotSerializer(serializers.Serializer):
    """Output serializer for a single available time slot."""
    start_time = serializers.DateTimeField(
        help_text="Slot start time (ISO 8601 format)"
    )
    end_time = serializers.DateTimeField(
        help_text="Slot end time (ISO 8601 format)"
    )
    available_staff = AvailableStaffSerializer(
        many=True,
        help_text="List of available staff members with full details"
    )
    available_staff_count = serializers.IntegerField(
        help_text="Number of staff members available for this slot"
    )


class ShopHoursSerializer(serializers.Serializer):
    """Serializer for shop hours information."""
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    slot_duration_minutes = serializers.IntegerField()
    day_of_week = serializers.CharField()


class DynamicAvailabilityResponseSerializer(serializers.Serializer):
    """
    Full response for dynamic availability check.
    
    Contains shop/service context, shop hours, and list of available slots.
    """
    shop_id = serializers.UUIDField(help_text="Shop UUID")
    shop_name = serializers.CharField(help_text="Shop name")
    shop_timezone = serializers.CharField(
        help_text="Shop timezone (IANA format, e.g., 'Asia/Karachi', 'Europe/London')"
    )
    service_id = serializers.UUIDField(help_text="Service UUID")
    service_name = serializers.CharField(help_text="Service name")
    service_duration_minutes = serializers.IntegerField(
        help_text="Service duration in minutes"
    )
    date = serializers.DateField(help_text="Target date")
    is_shop_open = serializers.BooleanField(
        help_text="Whether the shop is open on this date"
    )
    shop_hours = ShopHoursSerializer(
        required=False,
        allow_null=True,
        help_text="Shop hours for this date (null if closed)"
    )
    available_slots = AvailableSlotSerializer(
        many=True,
        help_text="List of available time slots"
    )
    total_available_slots = serializers.IntegerField(
        help_text="Total number of available slots"
    )
    eligible_staff_count = serializers.IntegerField(
        help_text="Number of staff members who can perform this service"
    )


# ============================================
# Holiday Serializers
# ============================================

class HolidaySerializer(serializers.ModelSerializer):
    """Serializer for Holiday model."""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    
    class Meta:
        from .models import Holiday
        model = Holiday
        fields = [
            'id', 'shop', 'shop_name', 'date', 'name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']


class HolidayCreateSerializer(serializers.Serializer):
    """
    Serializer for creating holidays.
    
    Supports multiple input formats:
    - dates: List of individual dates
    - start_date + end_date: Date range
    
    At least one format must be provided.
    """
    shop_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the shop"
    )
    dates = serializers.ListField(
        child=serializers.DateField(),
        required=False,
        min_length=1,
        help_text="List of dates to mark as holidays (e.g., ['2024-12-25', '2024-12-26'])"
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Start date for a range (inclusive)"
    )
    end_date = serializers.DateField(
        required=False,
        help_text="End date for a range (inclusive)"
    )
    name = serializers.CharField(
        max_length=100,
        required=False,
        default='',
        help_text="Optional name for the holiday (e.g., 'Christmas', 'Eid')"
    )
    
    class Meta:
        # OpenAPI example schemas
        examples = [
            {
                "name": "Multiple Dates",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "dates": ["2024-12-25", "2024-12-26"],
                    "name": "Christmas Holidays"
                }
            },
            {
                "name": "Date Range",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "start_date": "2024-12-24",
                    "end_date": "2024-12-31",
                    "name": "Winter Break"
                }
            },
            {
                "name": "Single Date",
                "value": {
                    "shop_id": "123e4567-e89b-12d3-a456-426614174000",
                    "dates": ["2024-01-01"],
                    "name": "New Year"
                }
            }
        ]
    
    def validate(self, data):
        dates = data.get('dates')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Must provide either dates list OR date range
        has_dates = dates is not None and len(dates) > 0
        has_range = start_date is not None and end_date is not None
        
        if not has_dates and not has_range:
            raise serializers.ValidationError(
                "Must provide either 'dates' (list of dates) or both 'start_date' and 'end_date'"
            )
        
        # Validate date range
        if has_range and start_date > end_date:
            raise serializers.ValidationError(
                "start_date must be before or equal to end_date"
            )
        
        return data
    
    def get_all_dates(self):
        """
        Get list of all dates from either dates list or range.
        
        Returns:
            List of date objects
        """
        from datetime import timedelta
        
        dates = self.validated_data.get('dates', [])
        start_date = self.validated_data.get('start_date')
        end_date = self.validated_data.get('end_date')
        
        all_dates = list(dates) if dates else []
        
        # Add dates from range
        if start_date and end_date:
            current = start_date
            while current <= end_date:
                if current not in all_dates:
                    all_dates.append(current)
                current += timedelta(days=1)
        
        # Remove duplicates and sort
        return sorted(set(all_dates))


class HolidayBulkResponseSerializer(serializers.Serializer):
    """Response serializer for bulk holiday creation."""
    message = serializers.CharField()
    holidays_created = serializers.IntegerField()
    holidays_skipped = serializers.IntegerField(
        help_text="Number of dates skipped (already exist)"
    )
    dates = serializers.ListField(child=serializers.DateField())
    shop_id = serializers.UUIDField()


class HolidayDeleteSerializer(serializers.Serializer):
    """Serializer for deleting holidays."""
    shop_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the shop"
    )
    dates = serializers.ListField(
        child=serializers.DateField(),
        required=False,
        help_text="List of specific dates to remove as holidays"
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Start date for a range to delete (inclusive)"
    )
    end_date = serializers.DateField(
        required=False,
        help_text="End date for a range to delete (inclusive)"
    )
    
    def validate(self, data):
        dates = data.get('dates')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Must provide either dates list OR date range
        has_dates = dates is not None and len(dates) > 0
        has_range = start_date is not None and end_date is not None
        
        if not has_dates and not has_range:
            raise serializers.ValidationError(
                "Must provide either 'dates' (list of dates) or both 'start_date' and 'end_date'"
            )
        
        if has_range and start_date > end_date:
            raise serializers.ValidationError(
                "start_date must be before or equal to end_date"
            )
        
        return data
    
    def get_all_dates(self):
        """Get list of all dates to delete."""
        from datetime import timedelta
        
        dates = self.validated_data.get('dates', [])
        start_date = self.validated_data.get('start_date')
        end_date = self.validated_data.get('end_date')
        
        all_dates = list(dates) if dates else []
        
        if start_date and end_date:
            current = start_date
            while current <= end_date:
                if current not in all_dates:
                    all_dates.append(current)
                current += timedelta(days=1)
        
        return sorted(set(all_dates))


class HolidayDeleteResponseSerializer(serializers.Serializer):
    """Response serializer for holiday deletion."""
    message = serializers.CharField()
    holidays_deleted = serializers.IntegerField()
    dates = serializers.ListField(child=serializers.DateField())
