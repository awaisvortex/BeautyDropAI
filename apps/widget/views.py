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
        summary="Get or update widget configuration by shop ID",
        description="""
        Get or update widget configuration for a specific shop (shop owners only).
        
        **GET:** Returns widget configuration. Auto-creates with defaults if doesn't exist.
        **PATCH:** Updates widget configuration with provided fields.
        
        For PATCH requests, you can upload images using multipart/form-data:
        - `banner_image`: Optional banner image file (JPEG, PNG, or WebP, max 5MB)
        - `logo`: Optional logo image file (JPEG, PNG, or WebP, max 5MB)
        
        Other fields can be included as form fields or JSON body.
        """,
        parameters=[
            OpenApiParameter(
                'shop_id',
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description='Shop ID to get/update widget configuration for'
            )
        ],
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'layout': {'type': 'string', 'enum': ['card', 'landscape', 'minimal']},
                    'primary_color': {'type': 'string', 'description': 'Hex color (e.g., #2563EB)'},
                    'widget_width': {'type': 'integer', 'minimum': 280, 'maximum': 800},
                    'border_radius': {'type': 'integer', 'maximum': 50},
                    'custom_title': {'type': 'string'},
                    'custom_description': {'type': 'string'},
                    'button_text': {'type': 'string', 'maxLength': 50},
                    'show_logo': {'type': 'boolean'},
                    'text_align': {'type': 'string', 'enum': ['left', 'center', 'right']},
                    'is_active': {'type': 'boolean'},
                    'banner_image': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Optional banner image (JPEG, PNG, or WebP, max 5MB)'
                    },
                    'logo': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Optional logo image (JPEG, PNG, or WebP, max 5MB)'
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'GET Response',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'shop': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Beauty Salon',
                    'layout': 'card',
                    'primary_color': '#2563EB',
                    'widget_width': 380,
                    'border_radius': 12,
                    'banner_image_url': 'http://localhost:8004/api/media/widgets/banners/abc123.jpg',
                    'logo_url': 'http://localhost:8004/api/media/widgets/logos/def456.png',
                    'button_text': 'Book Now',
                    'show_logo': True,
                    'text_align': 'center',
                    'is_active': True,
                    'created_at': '2024-12-01T10:00:00Z',
                    'updated_at': '2024-12-10T15:30:00Z'
                },
                response_only=True
            ),
            OpenApiExample(
                'PATCH Request (JSON only)',
                value={
                    'primary_color': '#FF5733',
                    'layout': 'landscape',
                    'button_text': 'Reserve Your Spot'
                },
                request_only=True
            ),
            OpenApiExample(
                'PATCH Response',
                value={
                    'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
                    'shop': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'layout': 'landscape',
                    'primary_color': '#FF5733',
                    'banner_image_url': 'http://localhost:8004/api/media/widgets/banners/abc123.jpg',
                    'button_text': 'Reserve Your Spot',
                    'updated_at': '2024-12-13T17:00:00Z'
                },
                response_only=True
            )
        ],
        responses={
            200: WidgetConfigurationSerializer,
            400: OpenApiResponse(description="Bad Request - Invalid file type or size"),
            403: OpenApiResponse(description="Forbidden - You don't own this shop"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Widget - Client']
    )
    @action(detail=False, methods=['get', 'patch'], url_path='shop/(?P<shop_id>[^/.]+)')
    def by_shop(self, request, shop_id=None):
        """Get or update widget configuration for a shop"""
        # Verify shop ownership
        shop = get_object_or_404(Shop, id=shop_id, client__user=request.user)
        
        if request.method == 'GET':
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
        
        elif request.method == 'PATCH':
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
            
            # Handle banner image upload
            banner_image_file = request.FILES.get('banner_image')
            if banner_image_file:
                from apps.core.services.storage_service import gcs_storage
                
                # Delete old image if exists
                if widget_config.banner_image_url:
                    self._delete_old_image(widget_config.banner_image_url, 'widgets/banners')
                
                # Upload new image
                banner_url = gcs_storage.upload_image(banner_image_file, folder='widgets/banners')
                if not banner_url:
                    return Response(
                        {'error': 'Failed to upload banner image. Please check file type and size.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                widget_config.banner_image_url = banner_url
            
            # Handle logo image upload
            logo_file = request.FILES.get('logo')
            if logo_file:
                from apps.core.services.storage_service import gcs_storage
                
                # Delete old image if exists
                if widget_config.logo_url:
                    self._delete_old_image(widget_config.logo_url, 'widgets/logos')
                
                # Upload new image
                logo_url = gcs_storage.upload_image(logo_file, folder='widgets/logos')
                if not logo_url:
                    return Response(
                        {'error': 'Failed to upload logo image. Please check file type and size.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                widget_config.logo_url = logo_url
            
            # Save image URL updates if any image was uploaded
            if banner_image_file or logo_file:
                update_fields = []
                if banner_image_file:
                    update_fields.append('banner_image_url')
                if logo_file:
                    update_fields.append('logo_url')
                widget_config.save(update_fields=update_fields)
            
            # Update with partial data (other fields from JSON)
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
                'Complete Preview Response',
                value={
                    'preview_url': 'http://localhost:8004/api/v1/widgets/shop/e188f3d1-921d-4261-9ea5-d6cfad62962a/preview/',
                    'preview_html': '<div class="widget-preview" style="width: 380px; border-radius: 12px; background-color: #ffffff; border: 2px solid #FF5733; padding: 20px; text-align: center;">\n  <h3>Elegant Beauty Salon</h3>\n  <p>Premium beauty services</p>\n  <button style="background-color: #FF5733; color: white; padding: 10px 20px; border: none; border-radius: 12px;">Reserve Now</button>\n</div>',
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
    
    def _delete_old_image(self, image_url: str, folder: str):
        """Delete old image from GCS bucket."""
        try:
            from apps.core.services.storage_service import gcs_storage
            import re
            
            # Extract filename from proxy URL
            # Format: http://backend/api/media/widgets/banners/filename.jpg
            match = re.search(rf'{folder}/(.+)$', image_url)
            if match:
                blob_name = f"{folder}/{match.group(1)}"
                blob = gcs_storage.bucket.blob(blob_name)
                if blob.exists():
                    blob.delete()
        except Exception as e:
            # Log but don't fail the update
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete old image: {e}")
