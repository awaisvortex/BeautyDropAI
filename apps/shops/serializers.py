"""
Shop serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
import pytz
from .models import Shop


class ShopSerializer(serializers.ModelSerializer):
    """Basic shop serializer"""
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    
    @extend_schema_field(serializers.IntegerField)
    def get_services_count(self, obj):
        return obj.services.filter(is_active=True).count()
    
    services_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = [
            'id', 'client', 'client_name', 'name', 'description',
            'address', 'city', 'state', 'postal_code', 'country',
            'phone', 'email', 'website', 'logo_url', 'cover_image_url',
            'timezone', 'is_active', 'services_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'client', 'created_at', 'updated_at']


class ShopDetailSerializer(ShopSerializer):
    """Detailed shop serializer with services"""
    
    @extend_schema_field(serializers.ListField)
    def get_services(self, obj):
        from apps.services.serializers import ServiceSerializer
        return ServiceSerializer(obj.services.filter(is_active=True), many=True).data
    
    services = serializers.SerializerMethodField()
    
    class Meta(ShopSerializer.Meta):
        fields = ShopSerializer.Meta.fields + ['services']


class ShopCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating shops"""
    
    class Meta:
        model = Shop
        fields = [
            'name', 'description', 'address', 'city', 'state',
            'postal_code', 'country', 'phone', 'email', 'website',
            'logo_url', 'cover_image_url', 'timezone', 'is_active'
        ]
    
    def validate_timezone(self, value):
        """Validate timezone is a valid pytz timezone."""
        try:
            pytz.timezone(value)
        except pytz.exceptions.UnknownTimeZoneError:
            raise serializers.ValidationError(
                f"Invalid timezone: {value}. Must be a valid IANA timezone (e.g., 'Asia/Karachi', 'Europe/London')"
            )
        return value


class ShopSearchSerializer(serializers.Serializer):
    """Serializer for shop search parameters"""
    query = serializers.CharField(required=False, help_text="Search query")
    city = serializers.CharField(required=False, help_text="Filter by city")
    service = serializers.CharField(required=False, help_text="Filter by service name")
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text="Minimum service price"
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text="Maximum service price"
    )
