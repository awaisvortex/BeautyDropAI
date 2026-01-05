"""
Payment app URLs for webhooks and Connect onboarding.
"""
from django.urls import path
from . import webhook_views, connect_views

app_name = 'payments'

urlpatterns = [
    # Webhooks
    path('webhooks/stripe/', webhook_views.stripe_webhook, name='stripe-webhook'),
    path('webhooks/clerk/', webhook_views.clerk_webhook, name='clerk-webhook'),
    
    # Stripe Connect onboarding for shop owners
    path('connect/create-account/', connect_views.create_connect_account, name='connect-create-account'),
    path('connect/account-link/', connect_views.get_account_link, name='connect-account-link'),
    path('connect/status/', connect_views.get_account_status, name='connect-status'),
    path('connect/dashboard/', connect_views.get_dashboard_link, name='connect-dashboard'),
]
