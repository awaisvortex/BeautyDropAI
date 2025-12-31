"""
Admin configuration for Scraper app
"""
from django.contrib import admin
from .models import ScrapeJob


@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'url_display', 'platform', 'status', 'shop', 'created_at']
    list_filter = ['status', 'platform', 'created_at']
    search_fields = ['url', 'client__user__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'raw_content', 'extracted_data']
    raw_id_fields = ['client', 'shop']
    
    def url_display(self, obj):
        """Truncate URL for display"""
        return obj.url[:60] + '...' if len(obj.url) > 60 else obj.url
    url_display.short_description = 'URL'
