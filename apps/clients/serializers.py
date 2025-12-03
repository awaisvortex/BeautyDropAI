"""
Client serializers
"""
from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Client
        fields = [
            'id', 'user', 'user_email', 'user_name', 'business_name',
            'business_description', 'tax_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating client profile"""
    
    class Meta:
        model = Client
        fields = ['business_name', 'business_description', 'tax_id']
