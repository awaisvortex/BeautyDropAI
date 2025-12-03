from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['user', 'business_name', 'created_at']
    search_fields = ['business_name', 'user__email']
    list_filter = ['created_at']
