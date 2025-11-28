"""
Notifications serializers
"""
from rest_framework import serializers
from .models import Notification
from apps.core.serializers import BaseSerializer


class NotificationSerializer(BaseSerializer):
    """
    Notification serializer
    """
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
