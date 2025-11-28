"""
Authentication serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    User serializer for API responses
    """
    @extend_schema_field(serializers.CharField)
    def get_full_name(self, obj):
        return obj.full_name
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
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
            'updated_at',
            'last_login_at',
        ]
        read_only_fields = [
            'id',
            'clerk_user_id',
            'email',
            'email_verified',
            'created_at',
            'updated_at',
            'last_login_at',
        ]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']


class UserRegistrationSerializer(serializers.Serializer):
    """
    Serializer for user registration (role selection)
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
