"""
Widget configuration model
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class WidgetConfiguration(BaseModel):
    """
    Embeddable booking widget configuration for shops.
    Shop owners can customize the appearance and behavior of their booking widget.
    """
    shop = models.OneToOneField(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='widget_config',
        help_text='Shop this widget configuration belongs to'
    )
    
    # Design & Layout
    LAYOUT_CHOICES = [
        ('card', 'Card'),
        ('landscape', 'Landscape'),
        ('minimal', 'Minimal'),
    ]
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default='card',
        help_text='Widget layout style'
    )
    
    primary_color = models.CharField(
        max_length=7,
        default='#2563EB',
        help_text='Primary color in hex format (e.g., #2563EB)'
    )
    
    widget_width = models.PositiveIntegerField(
        default=380,
        validators=[MinValueValidator(280), MaxValueValidator(800)],
        help_text='Widget width in pixels (280-800)'
    )
    
    border_radius = models.PositiveIntegerField(
        default=12,
        validators=[MaxValueValidator(50)],
        help_text='Border radius in pixels (0-50)'
    )
    
    # Content
    banner_image = models.URLField(
        blank=True,
        help_text='Banner image URL (overrides shop cover image)'
    )
    
    custom_title = models.CharField(
        max_length=255,
        blank=True,
        help_text='Custom title (defaults to shop name if empty)'
    )
    
    custom_description = models.TextField(
        blank=True,
        help_text='Custom description (defaults to shop description if empty)'
    )
    
    button_text = models.CharField(
        max_length=50,
        default='Book Now',
        help_text='Call-to-action button text'
    )
    
    logo_url = models.URLField(
        blank=True,
        help_text='Custom logo URL (overrides shop logo if provided)'
    )
    
    # Appearance
    show_logo = models.BooleanField(
        default=True,
        help_text='Display logo in widget'
    )
    
    TEXT_ALIGN_CHOICES = [
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
    ]
    text_align = models.CharField(
        max_length=10,
        choices=TEXT_ALIGN_CHOICES,
        default='center',
        help_text='Text alignment for widget content'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Widget is active and can be embedded'
    )
    
    class Meta:
        db_table = 'widget_configurations'
        verbose_name = 'Widget Configuration'
        verbose_name_plural = 'Widget Configurations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'is_active']),
        ]
    
    def __str__(self):
        return f"Widget Config for {self.shop.name}"
    
    def get_title(self):
        """Get display title (custom or shop name)"""
        return self.custom_title or self.shop.name
    
    def get_description(self):
        """Get display description (custom or shop description)"""
        return self.custom_description or self.shop.description
    
    def get_logo(self):
        """Get logo URL (custom or shop logo)"""
        return self.logo_url or self.shop.logo_url
