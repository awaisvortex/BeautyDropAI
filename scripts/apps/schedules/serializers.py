"""
Schedules serializers
"""
from rest_framework import serializers
from .models import ShopSchedule
from apps.core.serializers import BaseSerializer


class ShopScheduleSerializer(BaseSerializer):
    """
    ShopSchedule serializer
    """
    class Meta:
        model = ShopSchedule
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
