"""
Customers serializers
"""
from rest_framework import serializers
from .models import Customer
from apps.core.serializers import BaseSerializer


class CustomerSerializer(BaseSerializer):
    """
    Customer serializer
    """
    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
