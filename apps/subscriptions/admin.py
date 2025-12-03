from django.contrib import admin
from .models import Subscription, Payment


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan_type', 'status', 'start_date', 'end_date']
    search_fields = ['user__email']
    list_filter = ['status', 'plan_type', 'start_date']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'amount', 'status', 'payment_date']
    search_fields = ['subscription__user__email', 'transaction_id']
    list_filter = ['status', 'payment_date']
