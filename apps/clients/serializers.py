"""
Client serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Client
        fields = [
            'id', 'user', 'user_email', 'user_name', 'business_name',
            'phone', 'business_address', 'tax_id', 
            'subscription_status', 'subscription_plan', 'subscription_expires_at',
            'max_shops', 'scraping_limit', 'scraping_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating client profile"""
    
    class Meta:
        model = Client
        fields = ['business_name', 'phone', 'business_address', 'tax_id']


class ShopEarningsSerializer(serializers.Serializer):
    """Earnings breakdown for a single shop"""
    shop_id = serializers.UUIDField(help_text="Shop UUID")
    shop_name = serializers.CharField(help_text="Shop name")
    total_bookings = serializers.IntegerField(help_text="Total number of bookings")
    completed_bookings = serializers.IntegerField(help_text="Number of completed bookings")
    total_earnings = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Total earnings from completed bookings"
    )
    total_advance_payments = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Total advance payments received (deposits)"
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Client Total Earnings',
            value={
                'total_earnings': 15450.50,
                'total_advance_payments': 1545.05,
                'total_shops': 3,
                'total_completed_bookings': 156,
                'shops': [
                    {
                        'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                        'shop_name': 'Downtown Beauty Salon',
                        'total_bookings': 100,
                        'completed_bookings': 75,
                        'total_earnings': 8500.00,
                        'total_advance_payments': 850.00
                    },
                    {
                        'shop_id': 'f299g4e2-a32e-5372-0fb6-e7dgbe073f3b',
                        'shop_name': 'Uptown Spa',
                        'total_bookings': 80,
                        'completed_bookings': 56,
                        'total_earnings': 4950.50,
                        'total_advance_payments': 495.05
                    },
                    {
                        'shop_id': 'g310h5f3-b43f-6483-1gc7-f8ehcf184g4c',
                        'shop_name': 'Mall Salon',
                        'total_bookings': 40,
                        'completed_bookings': 25,
                        'total_earnings': 2000.00,
                        'total_advance_payments': 200.00
                    }
                ]
            },
            response_only=True
        )
    ]
)
class ClientTotalEarningsSerializer(serializers.Serializer):
    """Response serializer for client's total earnings across all shops"""
    total_earnings = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Grand total earnings from all shops"
    )
    total_advance_payments = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Grand total of advance payments received (deposits)"
    )
    total_shops = serializers.IntegerField(help_text="Number of shops owned")
    total_completed_bookings = serializers.IntegerField(
        help_text="Total completed bookings across all shops"
    )
    shops = ShopEarningsSerializer(many=True, help_text="Earnings breakdown per shop")
