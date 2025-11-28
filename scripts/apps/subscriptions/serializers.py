"""
Subscriptions serializers
"""
from rest_framework import serializers
from .models import Subscription
from apps.core.serializers import BaseSerializer


class SubscriptionSerializer(BaseSerializer):
    """
    Subscription serializer
    """
    class Meta:
        model = Subscription
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
