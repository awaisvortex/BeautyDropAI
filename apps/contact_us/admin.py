"""
Admin configuration for contact us app.
"""
from django.contrib import admin
from .models import ContactQuery


@admin.register(ContactQuery)
class ContactQueryAdmin(admin.ModelAdmin):
    """Admin interface for contact queries."""
    
    list_display = [
        'id',
        'first_name',
        'last_name',
        'email',
        'salon_name',
        'business_type',
        'team_size',
        'is_processed',
        'email_sent',
        'created_at',
    ]
    
    list_filter = [
        'is_processed',
        'email_sent',
        'business_type',
        'team_size',
        'best_time_to_reach',
        'created_at',
    ]
    
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'salon_name',
        'phone_number',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'email_sent',
    ]
    
    ordering = ['-created_at']
    
    fieldsets = (
        ('Contact Information', {
            'fields': (
                'id',
                ('first_name', 'last_name'),
                ('email', 'phone_number'),
            )
        }),
        ('Business Information', {
            'fields': (
                'salon_name',
                ('business_type', 'team_size'),
            )
        }),
        ('Inquiry Details', {
            'fields': (
                'challenges',
                'best_time_to_reach',
            )
        }),
        ('Status & Tracking', {
            'fields': (
                ('is_processed', 'email_sent'),
                'notes',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_processed', 'mark_as_unprocessed']
    
    @admin.action(description='Mark selected queries as processed')
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} queries marked as processed.')
    
    @admin.action(description='Mark selected queries as unprocessed')
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(is_processed=False)
        self.message_user(request, f'{updated} queries marked as unprocessed.')
