"""
Django Admin configuration for Calendar integrations
"""
from django.contrib import admin
from .models import CalendarIntegration, CalendarEvent


@admin.register(CalendarIntegration)
class CalendarIntegrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_connected', 'google_calendar_id', 'is_sync_enabled', 'last_sync_at']
    list_filter = ['is_sync_enabled']
    search_fields = ['user__email', 'user__full_name']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Google Calendar', {
            'fields': ('google_calendar_id', 'google_token_expires_at'),
            'description': 'OAuth tokens are hidden for security'
        }),
        ('Sync Settings', {
            'fields': ('is_sync_enabled', 'last_sync_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_connected(self, obj):
        return obj.is_connected
    is_connected.boolean = True
    is_connected.short_description = 'Connected'


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['booking', 'google_event_id', 'is_synced', 'last_synced_at']
    list_filter = ['is_synced']
    search_fields = ['booking__customer__user__email', 'google_event_id']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at']
    raw_id_fields = ['booking', 'integration']
