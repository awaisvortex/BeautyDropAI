"""
Service serializers
"""
from rest_framework import serializers
from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for Service model"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'shop', 'shop_name', 'name', 'description',
            'price', 'duration_minutes', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']


class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating services"""
    shop_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Service
        fields = ['shop_id', 'name', 'description', 'price', 'duration_minutes', 'is_active', 'category']
    
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
