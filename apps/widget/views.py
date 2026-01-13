"""
Widget configuration views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample, OpenApiTypes
from django.shortcuts import get_object_or_404

from apps.core.permissions import IsClient
from apps.shops.models import Shop
from .models import WidgetConfiguration
from .serializers import (
    WidgetConfigurationSerializer,
    WidgetConfigurationUpdateSerializer,
    WidgetPreviewRequestSerializer,
    WidgetPreviewResponseSerializer
)


class WidgetConfigurationViewSet(viewsets.ViewSet):
    """ViewSet for managing booking widget configurations (shop owner only)"""
    permission_classes = [IsAuthenticated, IsClient]
    
    @extend_schema(
        summary="Get widget configuration by shop ID",
        description="""
        Get widget configuration for a specific shop (shop owners only).
        
        If no widget configuration exists for the shop, a default one will be created automatically.
        This ensures every shop can have a widget without explicitly creating it first.
        """,
        parameters=[
            OpenApiParameter(
                'shop_id',
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description='Shop ID to get widget configuration for'
            )
        ],
        examples=[
            OpenApiExample(
                'Widget Configuration Response',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'shop': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Beauty Salon',
                    'layout': 'card',
                    'primary_color': '#2563EB',
                    'widget_width': 380,
                    'border_radius': 12,
                    'banner_image': '',
                    'custom_title': '',
                    'custom_description': '',
                    'button_text': 'Book Now',
                    'logo_url': '',
                    'show_logo': True,
                    'text_align': 'center',
                    'display_title': 'Elegant Beauty Salon',
                    'display_description': 'Premium beauty services',
                    'display_logo': 'https://example.com/logo.png',
                    'is_active': True,
                    'created_at': '2024-12-01T10:00:00Z',
                    'updated_at': '2024-12-10T15:30:00Z',
                    'embed_code': '<!-- BeautyDrop Booking Widget -->\\n<div id=\"bd-widget-abc\"></div>'
                },
                response_only=True
            )
        ],
        responses={
            200: WidgetConfigurationSerializer,
            403: OpenApiResponse(description="Forbidden - You don't own this shop"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Widget - Client']
    )
    @action(detail=False, methods=['get'], url_path='shop/(?P<shop_id>[^/.]+)')
    def get_by_shop(self, request, shop_id=None):
        """Get or create widget configuration for a shop"""
        # Verify shop ownership
        shop = get_object_or_404(Shop, id=shop_id, client__user=request.user)
        
        # Get or create widget configuration
        widget_config, created = WidgetConfiguration.objects.get_or_create(
            shop=shop,
            defaults={
                'layout': 'card',
                'primary_color': '#2563EB',
                'widget_width': 380,
                'border_radius': 12,
                'button_text': 'Book Now',
                'show_logo': True,
                'text_align': 'center',
                'is_active': True
            }
        )
        
        serializer = WidgetConfigurationSerializer(widget_config)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update widget configuration by shop ID",
        description="""
        Update widget configuration for a specific shop (shop owners only).
        
        Use partial update to change specific settings without affecting others.
        """,
        parameters=[
            OpenApiParameter(
                'shop_id',
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description='Shop ID to update widget configuration for'
            )
        ],
        request=WidgetConfigurationUpdateSerializer,
        examples=[
            OpenApiExample(
                'Update Request',
                value={
                    'primary_color': '#FF5733',
                    'layout': 'landscape',
                    'button_text': 'Reserve Your Spot'
                },
                request_only=True,
                description='Update widget color scheme and layout'
            ),
            OpenApiExample(
                'Updated Configuration Response',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'shop': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Beauty Salon',
                    'layout': 'landscape',
                    'primary_color': '#FF5733',
                    'button_text': 'Reserve Your Spot',
                    'widget_width': 380,
                    'is_active': True,
                    'updated_at': '2024-12-10T16:00:00Z'
                },
                response_only=True
            )
        ],
        responses={
            200: WidgetConfigurationSerializer,
            400: OpenApiResponse(description="Bad Request - Invalid data"),
            403: OpenApiResponse(description="Forbidden - You don't own this shop"),
            404: OpenApiResponse(description="Shop not found or widget configuration doesn't exist")
        },
        tags=['Widget - Client']
    )
    @action(detail=False, methods=['patch'], url_path='shop/(?P<shop_id>[^/.]+)')
    def update_by_shop(self, request, shop_id=None):
        """Update widget configuration for a shop"""
        # Verify shop ownership
        shop = get_object_or_404(Shop, id=shop_id, client__user=request.user)
        
        # Get widget configuration (must exist)
        try:
            widget_config = WidgetConfiguration.objects.get(shop=shop)
        except WidgetConfiguration.DoesNotExist:
            return Response(
                {
                    'error': 'Widget configuration not found for this shop',
                    'message': 'Use GET endpoint first to create a default configuration'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update with partial data
        serializer = WidgetConfigurationUpdateSerializer(
            widget_config,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return full updated configuration
        output_serializer = WidgetConfigurationSerializer(widget_config)
        return Response(output_serializer.data)
    
    @extend_schema(
        summary="Preview widget with temporary settings",
        description="""
        Generate preview data with temporary settings without saving (shop owners only).
        
        This endpoint accepts optional widget settings and returns preview data
        combining the saved configuration with temporary overrides.
        Useful for live preview in the widget configuration UI.
        """,
        parameters=[
            OpenApiParameter(
                'shop_id',
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description='Shop ID to preview widget for'
            )
        ],
        request=WidgetPreviewRequestSerializer,
        examples=[
            OpenApiExample(
                'Preview Request',
                value={
                    'primary_color': '#FF5733',
                    'layout': 'minimal',
                    'button_text': 'Reserve Now'
                },
                request_only=True,
                description='Preview with temporary color, layout, and button text'
            ),
            OpenApiExample(
                'Preview Response',
                value={
                    'preview_url': 'http://localhost:8004/api/v1/widgets/shop/shop-uuid/preview/',
                    'preview_html': '<div style=\"...\" class=\"widget-preview\">...</div>',
                    'settings': {
                        'layout': 'minimal',
                        'primary_color': '#FF5733',
                        'widget_width': 380,
                        'border_radius': 12,
                        'button_text': 'Reserve Now',
                        'show_logo': True,
                        'text_align': 'center'
                    }
                },
                response_only=True
            )
        ],
        responses={
            200: WidgetPreviewResponseSerializer,
            400: OpenApiResponse(description="Bad Request - Invalid settings"),
            403: OpenApiResponse(description="Forbidden - You don't own this shop"),
            404: OpenApiResponse(description="Shop or widget configuration not found")
        },
        tags=['Widget - Client']
    )
    @action(detail=False, methods=['post'], url_path='shop/(?P<shop_id>[^/.]+)/preview')
    def preview_by_shop(self, request, shop_id=None):
        """Generate preview with temporary settings for a shop's widget"""
        # Verify shop ownership
        shop = get_object_or_404(Shop, id=shop_id, client__user=request.user)
        
        # Get widget configuration
        try:
            widget_config = WidgetConfiguration.objects.get(shop=shop)
        except WidgetConfiguration.DoesNotExist:
            return Response(
                {
                    'error': 'Widget configuration not found for this shop',
                    'message': 'Use GET endpoint first to create a default configuration'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get temporary settings from request
        temp_serializer = WidgetPreviewRequestSerializer(data=request.data)
        temp_serializer.is_valid(raise_exception=True)
        temp_settings = temp_serializer.validated_data
        
        # Combine saved settings with temporary overrides
        combined_settings = {
            'layout': temp_settings.get('layout', widget_config.layout),
            'primary_color': temp_settings.get('primary_color', widget_config.primary_color),
            'widget_width': temp_settings.get('widget_width', widget_config.widget_width),
            'border_radius': temp_settings.get('border_radius', widget_config.border_radius),
            'show_logo': temp_settings.get('show_logo', widget_config.show_logo),
            'text_align': temp_settings.get('text_align', widget_config.text_align),
            'button_text': temp_settings.get('button_text', widget_config.button_text),
        }
        
        # Generate preview HTML
        preview_html = self._generate_preview_html(widget_config, combined_settings)
        
        from django.conf import settings
        preview_url = f"{settings.BACKEND_URL}/api/v1/widgets/shop/{shop_id}/preview/"
        
        return Response({
            'preview_url': preview_url,
            'preview_html': preview_html,
            'settings': combined_settings
        })
    
    def _generate_preview_html(self, widget_config, settings):
        """Generate HTML preview of the widget with given settings"""
        # Simple HTML preview - frontend will render the actual widget
        html = f'''
        <div class="widget-preview" style="
            width: {settings['widget_width']}px;
            border-radius: {settings['border_radius']}px;
            background-color: #ffffff;
            border: 2px solid {settings['primary_color']};
            padding: 20px;
            text-align: {settings['text_align']};
        ">
            <h3>{widget_config.get_title()}</h3>
            <p>{widget_config.get_description()}</p>
            <button style="
                background-color: {settings['primary_color']};
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: {settings['border_radius']}px;
            ">{settings['button_text']}</button>
        </div>
        '''
        return html
