"""
Staff serializers
"""
from rest_framework import serializers
from .models import StaffMember, StaffService
from apps.services.serializers import ServiceSerializer


class StaffServiceSerializer(serializers.ModelSerializer):
    """Serializer for staff-service relationship"""
    service_id = serializers.UUIDField(source='service.id', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_price = serializers.DecimalField(
        source='service.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = StaffService
        fields = ['id', 'service_id', 'service_name', 'service_price', 'is_primary']
        read_only_fields = ['id']


class StaffMemberSerializer(serializers.ModelSerializer):
    """Serializer for reading staff member data"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    assigned_services = StaffServiceSerializer(source='staff_services', many=True, read_only=True)
    total_bookings = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffMember
        fields = [
            'id', 'shop', 'shop_name', 'name', 'email', 'phone',
            'bio', 'profile_image_url', 'is_active',
            'assigned_services', 'total_bookings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']
    
    def get_total_bookings(self, obj):
        """Get total number of bookings for this staff member"""
        return obj.bookings.count() if hasattr(obj, 'bookings') else 0


class StaffMemberCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating staff members"""
    shop_id = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = StaffMember
        fields = [
            'shop_id', 'name', 'email', 'phone',
            'bio', 'profile_image_url', 'is_active'
        ]
    
    def validate_email(self, value):
        """Validate email is unique within the shop"""
        if value:
            shop_id = self.initial_data.get('shop_id')
            existing = StaffMember.objects.filter(
                shop_id=shop_id,
                email=value
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError("A staff member with this email already exists in this shop")
        return value


class StaffServiceAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning/removing services to/from staff"""
    service_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        help_text="List of service IDs to assign to this staff member"
    )
    is_primary = serializers.BooleanField(
        default=False,
        help_text="Set as primary staff for these services"
    )
    
    def validate_service_ids(self, value):
        """Ensure service IDs are not empty"""
        if not value:
            raise serializers.ValidationError("At least one service ID is required")
        return value


class StaffMemberDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with full service information"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_id = serializers.UUIDField(source='shop.id', read_only=True)
    assigned_services = StaffServiceSerializer(source='staff_services', many=True, read_only=True)
    total_bookings = serializers.SerializerMethodField()
    recent_bookings_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffMember
        fields = [
            'id', 'shop_id', 'shop_name', 'name', 'email', 'phone',
            'bio', 'profile_image_url', 'is_active',
            'assigned_services', 'total_bookings', 'recent_bookings_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_total_bookings(self, obj):
        """Get total number of bookings"""
        return obj.bookings.count() if hasattr(obj, 'bookings') else 0
    
    def get_recent_bookings_count(self, obj):
        """Get bookings in the last 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not hasattr(obj, 'bookings'):
            return 0
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        return obj.bookings.filter(created_at__gte=thirty_days_ago).count()
