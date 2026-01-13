from django.contrib import admin
from .models import WidgetConfiguration


@admin.register(WidgetConfiguration)
class WidgetConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'shop',
        'layout',
        'primary_color',
        'widget_width',
        'is_active',
        'created_at'
    ]
    list_filter = ['layout', 'is_active', 'text_align', 'show_logo']
    search_fields = ['shop__name', 'custom_title', 'custom_description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Shop Information', {
            'fields': ('id', 'shop', 'is_active')
        }),
        ('Design & Layout', {
            'fields': ('layout', 'primary_color', 'widget_width', 'border_radius')
        }),
        ('Content', {
            'fields': ('banner_image', 'custom_title', 'custom_description', 'button_text', 'logo_url')
        }),
        ('Appearance', {
            'fields': ('show_logo', 'text_align')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
