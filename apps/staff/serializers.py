"""
Staff serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Staff Member Response',
            value={
                'id': '550e8400-e29b-41d4-a716-446655440000',
                'shop': '660e8400-e29b-41d4-a716-446655440001',
                'shop_name': 'Glamour Salon',
                'name': 'Jane Smith',
                'email': 'jane@example.com',
                'phone': '+1234567890',
                'bio': 'Senior stylist with 10 years experience',
                'profile_image_url': 'https://example.com/images/jane.jpg',
                'is_active': True,
                'invite_status': 'accepted',
                'invite_sent_at': '2024-12-01T10:00:00Z',
                'invite_accepted_at': '2024-12-01T12:30:00Z',
                'assigned_services': [
                    {
                        'id': '770e8400-e29b-41d4-a716-446655440002',
                        'service_id': '880e8400-e29b-41d4-a716-446655440003',
                        'service_name': 'Haircut',
                        'service_price': '50.00',
                        'is_primary': True
                    }
                ],
                'total_bookings': 42,
                'created_at': '2024-12-01T10:00:00Z',
                'updated_at': '2024-12-09T15:00:00Z'
            },
            response_only=True
        )
    ]
)
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
            'invite_status', 'invite_sent_at', 'invite_accepted_at',
            'assigned_services', 'total_bookings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shop', 'invite_status', 'invite_sent_at', 'invite_accepted_at', 'created_at', 'updated_at']
    
    def get_total_bookings(self, obj):
        """Get total number of bookings for this staff member"""
        return obj.bookings.count() if hasattr(obj, 'bookings') else 0


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Create Staff Member',
            value={
                'shop_id': '660e8400-e29b-41d4-a716-446655440001',
                'name': 'Jane Smith',
                'email': 'jane@example.com',
                'phone': '+1234567890',
                'bio': 'Senior stylist with 10 years experience',
                'profile_image_url': 'https://example.com/images/jane.jpg',
                'is_active': True,
                'send_invite': True
            },
            request_only=True,
            description='Create a new staff member and send Clerk invitation email'
        )
    ]
)
class StaffMemberCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating staff members"""
    shop_id = serializers.UUIDField(write_only=True, required=True, help_text="UUID of the shop")
    send_invite = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Send Clerk invitation email to staff member"
    )
    
    class Meta:
        model = StaffMember
        fields = [
            'shop_id', 'name', 'email', 'phone',
            'bio', 'profile_image_url', 'is_active', 'send_invite'
        ]
    
    def validate_email(self, value):
        """Validate email is required and unique within the shop"""
        if not value:
            raise serializers.ValidationError("Email is required for staff invitation")
        
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
    
    def create(self, validated_data):
        """Create staff member, removing non-model fields"""
        # Remove non-model fields before creating
        validated_data.pop('send_invite', None)
        validated_data.pop('shop_id', None)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update staff member, removing non-model fields"""
        validated_data.pop('send_invite', None)
        validated_data.pop('shop_id', None)
        return super().update(instance, validated_data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Assign Services',
            value={
                'service_ids': [
                    '880e8400-e29b-41d4-a716-446655440003',
                    '990e8400-e29b-41d4-a716-446655440004'
                ],
                'is_primary': True
            },
            request_only=True,
            description='Assign multiple services to a staff member'
        )
    ]
)
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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Staff Member Detail Response',
            value={
                'id': '550e8400-e29b-41d4-a716-446655440000',
                'shop_id': '660e8400-e29b-41d4-a716-446655440001',
                'shop_name': 'Glamour Salon',
                'name': 'Jane Smith',
                'email': 'jane@example.com',
                'phone': '+1234567890',
                'bio': 'Senior stylist with 10 years experience',
                'profile_image_url': 'https://example.com/images/jane.jpg',
                'is_active': True,
                'invite_status': 'accepted',
                'invite_sent_at': '2024-12-01T10:00:00Z',
                'invite_accepted_at': '2024-12-01T12:30:00Z',
                'has_account': True,
                'assigned_services': [
                    {
                        'id': '770e8400-e29b-41d4-a716-446655440002',
                        'service_id': '880e8400-e29b-41d4-a716-446655440003',
                        'service_name': 'Haircut',
                        'service_price': '50.00',
                        'is_primary': True
                    }
                ],
                'total_bookings': 42,
                'recent_bookings_count': 8,
                'created_at': '2024-12-01T10:00:00Z',
                'updated_at': '2024-12-09T15:00:00Z'
            },
            response_only=True
        )
    ]
)
class StaffMemberDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with full service information"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_id = serializers.UUIDField(source='shop.id', read_only=True)
    assigned_services = StaffServiceSerializer(source='staff_services', many=True, read_only=True)
    total_bookings = serializers.SerializerMethodField()
    recent_bookings_count = serializers.SerializerMethodField()
    has_account = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffMember
        fields = [
            'id', 'shop_id', 'shop_name', 'name', 'email', 'phone',
            'bio', 'profile_image_url', 'is_active',
            'invite_status', 'invite_sent_at', 'invite_accepted_at', 'has_account',
            'assigned_services', 'total_bookings', 'recent_bookings_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_has_account(self, obj):
        """Check if staff member has linked user account"""
        return obj.user is not None
    
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

