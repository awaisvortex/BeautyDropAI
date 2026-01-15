"""
Serializers for contact us form.
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from .models import ContactQuery, BusinessType, TeamSize, BestTimeToReach


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Contact Form Submission',
            summary='Submit a consultation request',
            description='All fields are required for scheduling a free consultation',
            value={
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone_number': '915-268-1877',
                'salon_name': 'Glamour Beauty Salon',
                'business_type': 'hair_salon',
                'team_size': '3-5',
                'challenges': 'We miss a lot of calls during busy hours and clients have trouble booking appointments online.',
                'best_time_to_reach': 'morning'
            },
            request_only=True,
        ),
    ]
)
class ContactQueryCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new contact query.
    All fields are required.
    """
    first_name = serializers.CharField(
        max_length=100,
        help_text='Your first name',
        error_messages={
            'required': 'First name is required',
            'blank': 'First name cannot be blank'
        }
    )
    last_name = serializers.CharField(
        max_length=100,
        help_text='Your last name',
        error_messages={
            'required': 'Last name is required',
            'blank': 'Last name cannot be blank'
        }
    )
    email = serializers.EmailField(
        help_text='Your email address',
        error_messages={
            'required': 'Email address is required',
            'invalid': 'Please enter a valid email address'
        }
    )
    phone_number = serializers.CharField(
        max_length=20,
        help_text='Your phone number',
        error_messages={
            'required': 'Phone number is required',
            'blank': 'Phone number cannot be blank'
        }
    )
    salon_name = serializers.CharField(
        max_length=255,
        help_text='Name of your salon or spa',
        error_messages={
            'required': 'Salon/Spa name is required',
            'blank': 'Salon/Spa name cannot be blank'
        }
    )
    business_type = serializers.ChoiceField(
        choices=BusinessType.choices,
        help_text='Type of your beauty business. Options: nail_salon, day_spa, hair_salon, medical_spa, full_service, other',
        error_messages={
            'required': 'Business type is required',
            'invalid_choice': 'Please select a valid business type'
        }
    )
    team_size = serializers.ChoiceField(
        choices=TeamSize.choices,
        help_text='Number of team members. Options: 1-2, 3-5, 6-10, 11-20, 20+',
        error_messages={
            'required': 'Team size is required',
            'invalid_choice': 'Please select a valid team size'
        }
    )
    challenges = serializers.CharField(
        help_text='Describe your biggest challenges with phone calls and bookings',
        error_messages={
            'required': 'Please describe your challenges',
            'blank': 'Please describe your challenges'
        }
    )
    best_time_to_reach = serializers.ChoiceField(
        choices=BestTimeToReach.choices,
        help_text='Best time to reach you. Options: morning, afternoon, evening, anytime',
        error_messages={
            'required': 'Best time to reach is required',
            'invalid_choice': 'Please select a valid time option'
        }
    )
    
    class Meta:
        model = ContactQuery
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'salon_name',
            'business_type',
            'team_size',
            'challenges',
            'best_time_to_reach',
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Contact Form Response',
            summary='Successful submission response',
            description='Response after successfully submitting a consultation request',
            value={
                'id': '550e8400-e29b-41d4-a716-446655440000',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone_number': '915-268-1877',
                'salon_name': 'Glamour Beauty Salon',
                'business_type': 'hair_salon',
                'business_type_display': 'Hair Salon',
                'team_size': '3-5',
                'team_size_display': '3-5 team members',
                'challenges': 'We miss a lot of calls during busy hours and clients have trouble booking appointments online.',
                'best_time_to_reach': 'morning',
                'best_time_to_reach_display': 'Morning (9 AM - 12 PM)',
                'created_at': '2026-01-15T16:30:00Z',
                'message': 'Thank you for your interest! We will contact you soon.'
            },
            response_only=True,
        ),
    ]
)
class ContactQueryResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for contact query response.
    Includes display values for choice fields.
    """
    business_type_display = serializers.CharField(
        source='get_business_type_display',
        read_only=True,
        help_text='Human-readable business type'
    )
    team_size_display = serializers.CharField(
        source='get_team_size_display',
        read_only=True,
        help_text='Human-readable team size'
    )
    best_time_to_reach_display = serializers.CharField(
        source='get_best_time_to_reach_display',
        read_only=True,
        help_text='Human-readable best time to reach'
    )
    message = serializers.SerializerMethodField(
        help_text='Confirmation message'
    )
    
    class Meta:
        model = ContactQuery
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'salon_name',
            'business_type',
            'business_type_display',
            'team_size',
            'team_size_display',
            'challenges',
            'best_time_to_reach',
            'best_time_to_reach_display',
            'created_at',
            'message',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_message(self, obj):
        return "Thank you for your interest! We will contact you soon."
