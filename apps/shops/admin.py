from django.contrib import admin
from .models import Shop


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'city', 'is_active', 'created_at']
    search_fields = ['name', 'city', 'address']
    list_filter = ['is_active', 'created_at']
