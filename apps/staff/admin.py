"""
Staff admin configuration
"""
from django.contrib import admin
from .models import StaffMember, StaffService


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop', 'email', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active', 'shop', 'created_at']
    search_fields = ['name', 'email', 'phone', 'shop__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('shop', 'name', 'email', 'phone', 'is_active')
        }),
        ('Profile', {
            'fields': ('bio', 'profile_image_url')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StaffService)
class StaffServiceAdmin(admin.ModelAdmin):
    list_display = ['staff_member', 'service', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['staff_member__name', 'service__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
