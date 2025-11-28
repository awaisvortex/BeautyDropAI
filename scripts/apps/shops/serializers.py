"""
Shops serializers
"""
from rest_framework import serializers
from .models import Shop
from apps.core.serializers import BaseSerializer


class ShopSerializer(BaseSerializer):
    """
    Shop serializer
    """
    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
