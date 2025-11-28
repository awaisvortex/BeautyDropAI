from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop', 'price', 'duration_minutes', 'is_active']
    search_fields = ['name', 'shop__name']
    list_filter = ['is_active', 'created_at']
