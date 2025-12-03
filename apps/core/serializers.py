"""
Core serializers
"""
from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common configurations
    """
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
