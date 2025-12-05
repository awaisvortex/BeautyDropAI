"""
Service serializers
"""
from rest_framework import serializers
from .models import Service


class ServiceStaffSerializer(serializers.Serializer):
    """Serializer for staff members assigned to a service"""
    staff_id = serializers.UUIDField(source='staff_member.id', read_only=True)
    staff_name = serializers.CharField(source='staff_member.name', read_only=True)
    is_primary = serializers.BooleanField(read_only=True)


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for Service model"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    assigned_staff = ServiceStaffSerializer(source='service_staff', many=True, read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'shop', 'shop_name', 'name', 'description',
            'price', 'duration_minutes', 'buffer_minutes', 'category', 'image_url',
            'is_active', 'booking_count', 'assigned_staff', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']


class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating services"""
    shop_id = serializers.UUIDField(write_only=True, required=False)
    buffer_minutes = serializers.IntegerField(
        default=15,
        min_value=0,
        max_value=120,
        help_text='Minimum time buffer (minutes) before earliest bookable slot'
    )
    
    class Meta:
        model = Service
        fields = [
            'shop_id', 'name', 'description', 'price', 
            'duration_minutes', 'buffer_minutes', 'is_active', 'category'
        ]
    
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
    
    def validate_duration_minutes(self, value):
        if value < 15:
            raise serializers.ValidationError("Duration must be at least 15 minutes")
        if value > 480:  # 8 hours
            raise serializers.ValidationError("Duration cannot exceed 8 hours")
        return value

    def create(self, validated_data):
        validated_data.pop('shop_id', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('shop_id', None)
        return super().update(instance, validated_data)
