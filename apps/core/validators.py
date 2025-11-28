"""
Custom validators
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_phone_number(value):
    """
    Validate phone number format
    """
    phone_regex = re.compile(r'^\+?1?\d{9,15}$')
    if not phone_regex.match(value):
        raise ValidationError(
            _('Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.')
        )


def validate_postal_code(value):
    """
    Validate postal code format
    """
    if not re.match(r'^[A-Za-z0-9\s-]{3,10}$', value):
        raise ValidationError(
            _('Invalid postal code format.')
        )


def validate_positive_decimal(value):
    """
    Validate that decimal is positive
    """
    if value <= 0:
        raise ValidationError(
            _('Value must be greater than zero.')
        )


def validate_duration(value):
    """
    Validate duration in minutes (must be positive and reasonable)
    """
    if value <= 0 or value > 480:  # Max 8 hours
        raise ValidationError(
            _('Duration must be between 1 and 480 minutes.')
        )
