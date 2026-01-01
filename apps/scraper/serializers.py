"""
Serializers for Scraper API with proper Swagger documentation
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import ScrapeJob


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Submit URL',
            value={'url': 'https://example-salon.com'},
            request_only=True,
        ),
    ]
)
class ScrapeSubmitSerializer(serializers.Serializer):
    """Request serializer for submitting a URL to scrape"""
    url = serializers.URLField(
        required=True,
        max_length=2000,
        help_text="URL of the salon website to scrape"
    )
    
    def validate_url(self, value):
        """Validate the URL is accessible"""
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL must start with http:// or https://")
        return value


class ExtractedShopDataSerializer(serializers.Serializer):
    """Serializer for extracted shop data"""
    name = serializers.CharField(max_length=255, required=False, help_text="Shop/salon name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Shop description")
    address = serializers.CharField(max_length=500, required=False, allow_blank=True, help_text="Street address")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="City")
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="State/Province")
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, help_text="ZIP/Postal code")
    country = serializers.CharField(max_length=100, required=False, default='USA', help_text="Country")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, help_text="Phone number")
    email = serializers.EmailField(required=False, allow_blank=True, help_text="Email address")
    website = serializers.URLField(required=False, allow_blank=True, help_text="Website URL")
    timezone = serializers.CharField(max_length=63, required=False, default='UTC', help_text="Timezone (IANA format)")


class ExtractedServiceDataSerializer(serializers.Serializer):
    """Serializer for extracted service data"""
    name = serializers.CharField(max_length=255, required=True, help_text="Service name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Service description")
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True, help_text="Price in dollars")
    duration_minutes = serializers.IntegerField(min_value=15, max_value=480, required=True, help_text="Duration in minutes")
    category = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="Service category")


class ExtractedScheduleDataSerializer(serializers.Serializer):
    """Serializer for extracted schedule data"""
    day_of_week = serializers.ChoiceField(
        choices=['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
        required=True,
        help_text="Day of the week"
    )
    start_time = serializers.TimeField(required=False, allow_null=True, help_text="Opening time (HH:MM)")
    end_time = serializers.TimeField(required=False, allow_null=True, help_text="Closing time (HH:MM)")
    is_closed = serializers.BooleanField(required=False, default=False, help_text="True if closed on this day")


class ExtractedDealDataSerializer(serializers.Serializer):
    """Serializer for extracted deal data"""
    name = serializers.CharField(max_length=255, required=True, help_text="Deal/package name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Deal description")
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True, help_text="Bundle price")
    included_items = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=True,
        help_text="List of services/items included in the deal"
    )


class ExtractedDataSerializer(serializers.Serializer):
    """Nested serializer for all extracted data"""
    shop = ExtractedShopDataSerializer(required=False)
    services = ExtractedServiceDataSerializer(many=True, required=False)
    deals = ExtractedDealDataSerializer(many=True, required=False)
    schedule = ExtractedScheduleDataSerializer(many=True, required=False)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Completed Job',
            value={
                'id': '1d65492d-0ec0-4916-b8f4-9718a89bb3d3',
                'url': 'https://example-salon.com',
                'platform': 'generic',
                'status': 'completed',
                'extracted_data': {
                    'shop': {
                        'name': 'Example Salon',
                        'city': 'Los Angeles',
                        'phone': '+12025551234'
                    },
                    'services': [
                        {'name': 'Haircut', 'price': 45, 'duration_minutes': 60}
                    ],
                    'schedule': [
                        {'day_of_week': 'monday', 'start_time': '09:00', 'end_time': '18:00'}
                    ]
                },
                'error_message': '',
                'shop_id': None,
                'shop_name': None,
                'client_email': 'owner@salon.com',
                'created_at': '2025-12-31T08:00:00Z',
                'updated_at': '2025-12-31T08:01:00Z'
            },
            response_only=True,
        ),
    ]
)
class ScrapeJobSerializer(serializers.ModelSerializer):
    """Full response serializer for ScrapeJob with extracted data"""
    client_email = serializers.EmailField(source='client.user.email', read_only=True)
    shop_id = serializers.UUIDField(source='shop.id', read_only=True, allow_null=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True, allow_null=True)
    extracted_data = ExtractedDataSerializer(read_only=True)
    
    class Meta:
        model = ScrapeJob
        fields = [
            'id',
            'url',
            'platform',
            'status',
            'extracted_data',
            'error_message',
            'shop_id',
            'shop_name',
            'client_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class ScrapeJobListSerializer(serializers.ModelSerializer):
    """Compact serializer for listing scrape jobs"""
    
    class Meta:
        model = ScrapeJob
        fields = [
            'id',
            'url',
            'platform',
            'status',
            'created_at',
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Confirm with defaults',
            description='Use extracted data as-is',
            value={'use_extracted': True},
            request_only=True,
        ),
        OpenApiExample(
            'Override shop name',
            description='Override specific fields',
            value={
                'use_extracted': True,
                'shop_data': {'name': 'My Custom Shop Name'}
            },
            request_only=True,
        ),
    ]
)
class ScrapeConfirmSerializer(serializers.Serializer):
    """Request serializer for confirming and creating shop from scrape job"""
    use_extracted = serializers.BooleanField(
        default=True,
        help_text="If true, use extracted data as base. If false, only use provided data."
    )
    shop = ExtractedShopDataSerializer(
        required=False,
        help_text="Override extracted shop data"
    )
    services = ExtractedServiceDataSerializer(
        many=True,
        required=False,
        help_text="Override extracted services"
    )
    schedule = ExtractedScheduleDataSerializer(
        many=True,
        required=False,
        help_text="Override extracted schedule"
    )


class ScrapeConfirmResponseSerializer(serializers.Serializer):
    """Response serializer for confirm endpoint"""
    success = serializers.BooleanField(help_text="Whether shop was created successfully")
    shop_id = serializers.UUIDField(help_text="ID of the created shop")
    shop_name = serializers.CharField(help_text="Name of the created shop")
    services_created = serializers.IntegerField(help_text="Number of services created")
    schedules_created = serializers.IntegerField(help_text="Number of schedule entries created")


class ScrapeSubmitResponseSerializer(serializers.Serializer):
    """Response serializer for submit endpoint"""
    id = serializers.UUIDField(help_text="Scrape job ID")
    url = serializers.URLField(help_text="URL being scraped")
    platform = serializers.CharField(help_text="Detected platform (google_business, yelp, generic, etc.)")
    status = serializers.CharField(help_text="Job status (pending, scraping, parsing, completed, failed)")
    created_at = serializers.DateTimeField(help_text="Job creation time")
