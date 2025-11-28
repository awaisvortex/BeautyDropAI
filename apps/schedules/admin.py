from django.contrib import admin
from .models import ShopSchedule, TimeSlot


@admin.register(ShopSchedule)
class ShopScheduleAdmin(admin.ModelAdmin):
    list_display = ['shop', 'day_of_week', 'start_time', 'end_time', 'is_active']
    search_fields = ['shop__name']
    list_filter = ['day_of_week', 'is_active']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['schedule', 'start_datetime', 'end_datetime', 'status']
    search_fields = ['schedule__shop__name']
    list_filter = ['status', 'start_datetime']
