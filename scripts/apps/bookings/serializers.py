"""
Bookings serializers
"""
from rest_framework import serializers
from .models import Booking
from apps.core.serializers import BaseSerializer


class BookingSerializer(BaseSerializer):
    """
    Booking serializer
    """
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
