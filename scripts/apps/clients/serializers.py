"""
Clients serializers
"""
from rest_framework import serializers
from .models import Client
from apps.core.serializers import BaseSerializer


class ClientSerializer(BaseSerializer):
    """
    Client serializer
    """
    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
