"""
Customer serializers
"""
from rest_framework import serializers
from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    favorite_shops_count = serializers.IntegerField(
        source='favorite_shops.count',
        read_only=True
    )
    
    class Meta:
        model = Customer
        fields = [
            'id', 'user', 'user_email', 'user_name', 'phone',
            'date_of_birth', 'subscription_status', 'subscription_plan',
            'subscription_expires_at', 'favorite_shops_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'subscription_status', 'subscription_plan',
            'subscription_expires_at', 'created_at', 'updated_at'
        ]


class CustomerUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating customer profile"""
    
    class Meta:
        model = Customer
        fields = ['phone', 'date_of_birth']
