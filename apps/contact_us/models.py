"""
Contact Us models for consultation form submissions.
"""
from django.db import models
from apps.core.models import BaseModel


class BusinessType(models.TextChoices):
    """Business type choices for salon/spa"""
    NAIL_SALON = 'nail_salon', 'Nail Salon'
    DAY_SPA = 'day_spa', 'Day Spa'
    HAIR_SALON = 'hair_salon', 'Hair Salon'
    MEDICAL_SPA = 'medical_spa', 'Medical Spa'
    FULL_SERVICE = 'full_service', 'Full-Service Beauty Salon'
    OTHER = 'other', 'Other'


class TeamSize(models.TextChoices):
    """Team size choices"""
    SIZE_1_2 = '1-2', '1-2 team members'
    SIZE_3_5 = '3-5', '3-5 team members'
    SIZE_6_10 = '6-10', '6-10 team members'
    SIZE_11_20 = '11-20', '11-20 team members'
    SIZE_20_PLUS = '20+', '20+ team members'


class BestTimeToReach(models.TextChoices):
    """Best time to reach choices"""
    MORNING = 'morning', 'Morning (9 AM - 12 PM)'
    AFTERNOON = 'afternoon', '12 PM - 5 PM'
    EVENING = 'evening', 'Evening (5 PM - 8 PM)'
    ANYTIME = 'anytime', 'Anytime'


class ContactQuery(BaseModel):
    """
    Stores contact/consultation form submissions.
    Each query has a UUID for tracking and all form data.
    """
    # Personal Information
    first_name = models.CharField(
        max_length=100,
        help_text='First name of the person'
    )
    last_name = models.CharField(
        max_length=100,
        help_text='Last name of the person'
    )
    email = models.EmailField(
        help_text='Email address for contact'
    )
    phone_number = models.CharField(
        max_length=20,
        help_text='Phone number for contact'
    )
    
    # Business Information
    salon_name = models.CharField(
        max_length=255,
        help_text='Name of the salon/spa'
    )
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        help_text='Type of beauty business'
    )
    team_size = models.CharField(
        max_length=10,
        choices=TeamSize.choices,
        help_text='Number of team members'
    )
    
    # Inquiry Details
    challenges = models.TextField(
        help_text='Description of challenges with phone calls and bookings'
    )
    best_time_to_reach = models.CharField(
        max_length=10,
        choices=BestTimeToReach.choices,
        help_text='Best time to reach the person'
    )
    
    # Tracking Fields
    is_processed = models.BooleanField(
        default=False,
        help_text='Whether the query has been followed up'
    )
    email_sent = models.BooleanField(
        default=False,
        help_text='Whether notification email was sent successfully'
    )
    notes = models.TextField(
        blank=True,
        help_text='Internal notes for follow-up'
    )
    
    class Meta:
        db_table = 'contact_queries'
        verbose_name = 'Contact Query'
        verbose_name_plural = 'Contact Queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Contact Query from {self.first_name} {self.last_name} ({self.email})"
