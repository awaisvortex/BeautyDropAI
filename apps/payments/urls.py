"""
Payment app URLs for webhooks.
"""
from django.urls import path
from . import webhook_views

app_name = 'payments'

urlpatterns = [
    path('webhooks/stripe/', webhook_views.stripe_webhook, name='stripe-webhook'),
    path('webhooks/clerk/', webhook_views.clerk_webhook, name='clerk-webhook'),
]
