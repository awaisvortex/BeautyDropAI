"""
Serializers for Scraper API with proper Swagger documentation
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import ScrapeJob


# ============================================================
# Input Serializers
# ============================================================

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
    duration_minutes = serializers.IntegerField(
        min_value=15, max_value=480, required=False, default=60,
        help_text="Total duration for the deal booking in minutes (default 60)"
    )
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
            'Confirm with extracted data',
            description='Use extracted shop data as-is',
            value={
                'shop': {
                    'name': 'Example Salon',
                    'city': 'Los Angeles',
                    'phone': '+12025551234'
                }
            },
            request_only=True,
        ),
        OpenApiExample(
            'Confirm with edits',
            description='Modify extracted data before creating',
            value={
                'shop': {
                    'name': 'My Custom Salon Name',
                    'city': 'New York',
                    'phone': '+19005551234'
                },
                'services': [
                    {'name': 'Premium Haircut', 'price': 55, 'duration_minutes': 45}
                ]
            },
            request_only=True,
        ),
    ]
)
class ScrapeConfirmSerializer(serializers.Serializer):
    """
    Request serializer for confirming and creating shop from scrape job.
    
    Always requires shop data (either extracted or edited by owner).
    Pass the extracted data as-is or modify it before confirming.
    """
    shop = ExtractedShopDataSerializer(
        required=True,
        help_text="Shop data (extracted or edited). Name is required."
    )
    services = ExtractedServiceDataSerializer(
        many=True,
        required=False,
        help_text="Services to create (pass extracted or edited list)"
    )
    schedule = ExtractedScheduleDataSerializer(
        many=True,
        required=False,
        help_text="Schedule entries (pass extracted or edited list)"
    )
    deals = ExtractedDealDataSerializer(
        many=True,
        required=False,
        help_text="Deals to create (pass extracted or edited list)"
    )
    
    def validate_shop(self, value):
        """Ensure shop name is provided."""
        if not value.get('name'):
            raise serializers.ValidationError("Shop name is required")
        return value


# ============================================================
# Response Serializers
# ============================================================

class ScrapingLimitInfoSerializer(serializers.Serializer):
    """Serializer for scraping limit information"""
    scraping_count = serializers.IntegerField(help_text="Number of completed scrape jobs")
    scraping_limit = serializers.IntegerField(help_text="Maximum allowed scrape jobs")
    scraping_remaining = serializers.IntegerField(help_text="Remaining scraping quota")


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
                'scraping_count': 3,
                'scraping_limit': 5,
                'scraping_remaining': 2,
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
    
    # Scraping limit info from client
    scraping_count = serializers.IntegerField(source='client.scraping_count', read_only=True)
    scraping_limit = serializers.IntegerField(source='client.scraping_limit', read_only=True)
    scraping_remaining = serializers.SerializerMethodField()
    
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
            'scraping_count',
            'scraping_limit',
            'scraping_remaining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_scraping_remaining(self, obj):
        return max(0, obj.client.scraping_limit - obj.client.scraping_count)


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


class ScrapeSubmitResponseSerializer(serializers.Serializer):
    """Response serializer for submit endpoint"""
    id = serializers.UUIDField(help_text="Scrape job ID")
    url = serializers.URLField(help_text="URL being scraped")
    platform = serializers.CharField(help_text="Detected platform (google_business, yelp, generic, etc.)")
    status = serializers.CharField(help_text="Job status (pending, scraping, parsing, completed, failed)")
    scraping_count = serializers.IntegerField(help_text="Number of completed scrape jobs")
    scraping_limit = serializers.IntegerField(help_text="Maximum allowed scrape jobs")
    scraping_remaining = serializers.IntegerField(help_text="Remaining scraping quota")
    created_at = serializers.DateTimeField(help_text="Job creation time")


class ScrapeConfirmResponseSerializer(serializers.Serializer):
    """Response serializer for confirm endpoint"""
    success = serializers.BooleanField(help_text="Whether shop was created successfully")
    message = serializers.CharField(help_text="Status message")
    job_id = serializers.UUIDField(help_text="Scrape job ID")
    status = serializers.CharField(help_text="Current job status")
    services_count = serializers.IntegerField(help_text="Number of services to be created")
    deals_count = serializers.IntegerField(help_text="Number of deals to be created")


class ScrapingLimitErrorSerializer(serializers.Serializer):
    """Response serializer for scraping limit exceeded error"""
    error = serializers.CharField(help_text="Error message")
    scraping_count = serializers.IntegerField(help_text="Number of completed scrape jobs")
    scraping_limit = serializers.IntegerField(help_text="Maximum allowed scrape jobs")
    scraping_remaining = serializers.IntegerField(help_text="Remaining scraping quota (always 0)")


class ScrapingLimitsResponseSerializer(serializers.Serializer):
    """Response serializer for GET /limits/ endpoint"""
    scraping_count = serializers.IntegerField(help_text="Number of completed scrape jobs")
    scraping_limit = serializers.IntegerField(help_text="Maximum allowed scrape jobs")
    scraping_remaining = serializers.IntegerField(help_text="Remaining scraping quota")
