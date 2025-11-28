"""
Schedules admin configuration
"""
from django.contrib import admin
from .models import ShopSchedule


@admin.register(ShopSchedule)
class ShopScheduleAdmin(admin.ModelAdmin):
    """
    Admin configuration for ShopSchedule
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
