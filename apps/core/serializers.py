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


class MessageSerializer(serializers.Serializer):
    """Simple message response"""
    message = serializers.CharField()


class SuccessResponseSerializer(serializers.Serializer):
    """Standard success response with message"""
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response with error type and message"""
    error = serializers.CharField()
    message = serializers.CharField()
