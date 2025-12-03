"""
Authentication serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import User
from .services.user_data_service import user_data_service


class UserSerializer(serializers.ModelSerializer):
    """
    User serializer for API responses.
    Includes real-time fields fetched from Clerk API.
    """
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    
    @extend_schema_field(serializers.CharField)
    def get_full_name(self, obj):
        return obj.full_name
    
    @extend_schema_field(serializers.URLField)
    def get_avatar_url(self, obj):
        """Fetch avatar URL in real-time from Clerk"""
        return user_data_service.get_user_avatar(obj.clerk_user_id)
    
    @extend_schema_field(serializers.CharField)
    def get_phone(self, obj):
        """Fetch phone number in real-time from Clerk"""
        return user_data_service.get_user_phone(obj.clerk_user_id)
    
    class Meta:
        model = User
        fields = [
            'clerk_user_id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone',
            'avatar_url',
            'role',
            'is_active',
            'email_verified',
            'created_at',
        ]
        read_only_fields = [
            'clerk_user_id',
            'email',
            'email_verified',
            'created_at',
        ]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile.
    Note: Phone and avatar are managed by Clerk, not stored in our DB.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name']


class UserRegistrationSerializer(serializers.Serializer):
    """
    Serializer for user role selection
    """
    role = serializers.ChoiceField(choices=['client', 'customer'])
    
    def update_user_role(self, user):
        """Update user role"""
        user.role = self.validated_data['role']
        user.save(update_fields=['role'])
        return user


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check response"""
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    database = serializers.CharField()
    cache = serializers.CharField()
