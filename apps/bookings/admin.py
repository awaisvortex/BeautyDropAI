from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['customer', 'service', 'booking_datetime', 'status']
    search_fields = ['customer__user__email', 'service__name']
    list_filter = ['status', 'booking_datetime', 'created_at']
