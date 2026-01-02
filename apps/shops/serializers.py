"""
Shop serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
import pytz
import json
from .models import Shop


class AddressSerializer(serializers.Serializer):
    """Serializer for structured address input"""
    street = serializers.CharField(required=True, allow_blank=True, help_text="Street address")
    city = serializers.CharField(required=True, allow_blank=True, help_text="City")
    state = serializers.CharField(required=False, allow_blank=True, default='', help_text="State/Province")
    postal_code = serializers.CharField(required=True, allow_blank=True, help_text="Postal/ZIP code")
    country = serializers.CharField(required=False, default='USA', help_text="Country")


class ShopSerializer(serializers.ModelSerializer):
    """Basic shop serializer"""
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    
    # Return address as structured object
    address = serializers.SerializerMethodField()
    
    @extend_schema_field(serializers.IntegerField)
    def get_services_count(self, obj):
        return obj.services.filter(is_active=True).count()
    
    @extend_schema_field(AddressSerializer)
    def get_address(self, obj):
        return {
            'street': obj.address,
            'city': obj.city,
            'state': obj.state,
            'postal_code': obj.postal_code,
            'country': obj.country,
        }
    
    services_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = [
            'id', 'client', 'client_name', 'name', 'description',
            'address', 'phone', 'email', 'website', 'logo_url', 'cover_image_url',
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
    
    # Accept address as JSON object or string
    address = serializers.JSONField(required=True, help_text="Address as JSON object: {'street': '', 'city': '', 'state': '', 'postal_code': '', 'country': ''}")
    
    class Meta:
        model = Shop
        fields = [
            'name', 'description', 'address', 'phone', 'email', 'website',
            'logo_url', 'cover_image_url', 'timezone', 'is_active'
        ]
    
    def validate_address(self, value):
        """Validate and parse address field - accepts JSON object or plain string"""
        if isinstance(value, str):
            # Try to parse as JSON string first
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Treat as plain street address string
                return {
                    'street': value,
                    'city': '',
                    'state': '',
                    'postal_code': '',
                    'country': 'USA',
                }
        
        if isinstance(value, dict):
            # Validate the structure
            address_serializer = AddressSerializer(data=value)
            if not address_serializer.is_valid():
                raise serializers.ValidationError(address_serializer.errors)
            return address_serializer.validated_data
        
        raise serializers.ValidationError(
            "Address must be a JSON object with keys: street, city, state, postal_code, country"
        )
    
    def validate_timezone(self, value):
        """Validate timezone is a valid pytz timezone."""
        try:
            pytz.timezone(value)
        except pytz.exceptions.UnknownTimeZoneError:
            raise serializers.ValidationError(
                f"Invalid timezone: {value}. Must be a valid IANA timezone (e.g., 'Asia/Karachi', 'Europe/London')"
            )
        return value
    
    def create(self, validated_data):
        """Create shop with parsed address fields"""
        address_data = validated_data.pop('address', {})
        
        # Map address fields to model fields
        validated_data['address'] = address_data.get('street', '')
        validated_data['city'] = address_data.get('city', '')
        validated_data['state'] = address_data.get('state', '')
        validated_data['postal_code'] = address_data.get('postal_code', '')
        validated_data['country'] = address_data.get('country', 'USA')
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update shop with parsed address fields"""
        address_data = validated_data.pop('address', None)
        
        if address_data:
            # Map address fields to model fields
            validated_data['address'] = address_data.get('street', instance.address)
            validated_data['city'] = address_data.get('city', instance.city)
            validated_data['state'] = address_data.get('state', instance.state)
            validated_data['postal_code'] = address_data.get('postal_code', instance.postal_code)
            validated_data['country'] = address_data.get('country', instance.country)
        
        return super().update(instance, validated_data)


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
