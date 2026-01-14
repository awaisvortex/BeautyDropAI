"""
Widget configuration serializers
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import WidgetConfiguration
import re


class WidgetConfigurationSerializer(serializers.ModelSerializer):
    """Output serializer for widget configuration"""
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_id = serializers.UUIDField(source='shop.id', read_only=True)
    embed_code = serializers.SerializerMethodField()
    display_title = serializers.SerializerMethodField()
    display_description = serializers.SerializerMethodField()
    display_logo = serializers.SerializerMethodField()
    
    class Meta:
        model = WidgetConfiguration
        fields = [
            'id', 'shop', 'shop_id', 'shop_name',
            # Design & Layout
            'layout', 'primary_color', 'widget_width', 'border_radius',
            # Content
            'banner_image_url', 'custom_title', 'custom_description',
            'button_text', 'logo_url',
            # Appearance
            'show_logo', 'text_align',
            # Computed fields
            'display_title', 'display_description', 'display_logo',
            # Status
            'is_active',
            # Metadata
            'created_at', 'updated_at',
            # Embed code
            'embed_code'
        ]
        read_only_fields = ['id', 'shop', 'created_at', 'updated_at']
    
    def get_embed_code(self, obj):
        """Generate embeddable HTML/JavaScript code snippet"""
        from django.conf import settings
        widget_id = str(obj.id)
        backend_url = settings.BACKEND_URL
        
        embed_html = f'''<!-- BeautyDrop Booking Widget -->
<div id="bd-widget-{widget_id}" data-widget-id="{widget_id}"></div>
<script>
  (function() {{
    var script = document.createElement('script');
    script.src = '{backend_url}/api/v1/widgets/script.js';
    script.async = true;
    document.head.appendChild(script);
  }})();
</script>'''
        return embed_html
    
    def get_display_title(self, obj):
        """Get the title that will be displayed in the widget"""
        return obj.get_title()
    
    def get_display_description(self, obj):
        """Get the description that will be displayed in the widget"""
        return obj.get_description()
    
    def get_display_logo(self, obj):
        """Get the logo URL that will be displayed in the widget"""
        return obj.get_logo()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Update Colors and Layout',
            value={
                'primary_color': '#FF5733',
                'layout': 'landscape',
                'button_text': 'Reserve Your Spot'
            },
            request_only=True,
            description='Update widget color scheme and layout'
        ),
        OpenApiExample(
            'Update Content Only',
            value={
                'custom_title': 'Premium Beauty Services',
                'custom_description': 'Experience luxury treatments by expert professionals',
                'banner_image': 'https://example.com/new-banner.jpg'
            },
            request_only=True,
            description='Update widget text and imagery'
        )
    ]
)
class WidgetConfigurationUpdateSerializer(serializers.ModelSerializer):
    """Input serializer for updating widget configurations"""
    
    class Meta:
        model = WidgetConfiguration
        fields = [
            'layout', 'primary_color', 'widget_width', 'border_radius',
            'custom_title', 'custom_description', 'button_text',
            'show_logo', 'text_align', 'is_active'
        ]
    
    def validate_primary_color(self, value):
        """Validate hex color format (#RRGGBB)"""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError(
                "Color must be in hex format (e.g., #2563EB)"
            )
        return value
    
    def validate_widget_width(self, value):
        """Ensure reasonable widget dimensions"""
        if value < 280 or value > 800:
            raise serializers.ValidationError(
                "Widget width must be between 280 and 800 pixels"
            )
        return value
    
    def validate_border_radius(self, value):
        """Ensure reasonable border radius"""
        if value > 50:
            raise serializers.ValidationError(
                "Border radius must be 50 pixels or less"
            )
        return value


class WidgetPreviewRequestSerializer(serializers.Serializer):
    """Input serializer for preview endpoint - allows temporary settings"""
    layout = serializers.ChoiceField(
        choices=['card', 'landscape', 'minimal'],
        required=False,
        help_text="Temporary layout to preview"
    )
    primary_color = serializers.CharField(
        required=False,
        help_text="Temporary primary color to preview (hex format)"
    )
    widget_width = serializers.IntegerField(
        required=False,
        help_text="Temporary widget width to preview"
    )
    border_radius = serializers.IntegerField(
        required=False,
        help_text="Temporary border radius to preview"
    )
    show_logo = serializers.BooleanField(
        required=False,
        help_text="Temporarily show/hide logo"
    )
    text_align = serializers.ChoiceField(
        choices=['left', 'center', 'right'],
        required=False,
        help_text="Temporary text alignment to preview"
    )
    button_text = serializers.CharField(
        required=False,
        max_length=50,
        help_text="Temporary button text to preview"
    )


class WidgetPreviewResponseSerializer(serializers.Serializer):
    """Output serializer for preview data"""
    preview_url = serializers.URLField(
        help_text="URL to preview the widget with temporary settings"
    )
    preview_html = serializers.CharField(
        help_text="HTML preview of the widget with applied settings"
    )
    settings = serializers.DictField(
        help_text="Combined settings (saved + temporary) used for preview"
    )
