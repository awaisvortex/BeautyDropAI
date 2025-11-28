"""
Services serializers
"""
from rest_framework import serializers
from .models import Service
from apps.core.serializers import BaseSerializer


class ServiceSerializer(BaseSerializer):
    """
    Service serializer
    """
    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
