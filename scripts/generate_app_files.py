"""
Script to generate boilerplate files for all Django apps
Run this script to create all necessary app files
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# App configurations
APPS = {
    'clients': {
        'model_name': 'Client',
        'has_services': True,
    },
    'customers': {
        'model_name': 'Customer',
        'has_services': True,
    },
    'shops': {
        'model_name': 'Shop',
        'has_services': True,
        'has_filters': True,
    },
    'services': {
        'model_name': 'Service',
        'has_services': True,
    },
    'schedules': {
        'model_name': 'ShopSchedule',
        'has_services': True,
        'has_utils': True,
    },
    'bookings': {
        'model_name': 'Booking',
        'has_services': True,
        'has_signals': True,
    },
    'subscriptions': {
        'model_name': 'Subscription',
        'has_services': True,
        'has_webhooks': True,
    },
    'notifications': {
        'model_name': 'Notification',
        'has_services': True,
    },
}


def create_file(filepath, content):
    """Create a file with content"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {filepath}")


def generate_app_files(app_name, config):
    """Generate all files for an app"""
    app_dir = BASE_DIR / 'apps' / app_name
    model_name = config['model_name']
    
    # __init__.py
    create_file(app_dir / '__init__.py', '')
    
    # apps.py
    apps_content = f'''"""
{app_name.capitalize()} app configuration
"""
from django.apps import AppConfig


class {app_name.capitalize()}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.{app_name}'
'''
    create_file(app_dir / 'apps.py', apps_content)
    
    # serializers.py
    serializers_content = f'''"""
{app_name.capitalize()} serializers
"""
from rest_framework import serializers
from .models import {model_name}
from apps.core.serializers import BaseSerializer


class {model_name}Serializer(BaseSerializer):
    """
    {model_name} serializer
    """
    class Meta:
        model = {model_name}
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
'''
    create_file(app_dir / 'serializers.py', serializers_content)
    
    # views.py
    views_content = f'''"""
{app_name.capitalize()} views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import {model_name}
from .serializers import {model_name}Serializer


class {model_name}ViewSet(viewsets.ModelViewSet):
    """
    ViewSet for {model_name}
    """
    queryset = {model_name}.objects.all()
    serializer_class = {model_name}Serializer
    permission_classes = [IsAuthenticated]
'''
    create_file(app_dir / 'views.py', views_content)
    
    # urls.py
    urls_content = f'''"""
{app_name.capitalize()} URL patterns
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = '{app_name}'

router = DefaultRouter()
router.register(r'', views.{model_name}ViewSet, basename='{app_name.rstrip("s")}')

urlpatterns = [
    path('', include(router.urls)),
]
'''
    create_file(app_dir / 'urls.py', urls_content)
    
    # admin.py
    admin_content = f'''"""
{app_name.capitalize()} admin configuration
"""
from django.contrib import admin
from .models import {model_name}


@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    """
    Admin configuration for {model_name}
    """
    list_display = ['id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['id']
    ordering = ['-created_at']
'''
    create_file(app_dir / 'admin.py', admin_content)
    
    # permissions.py
    permissions_content = f'''"""
{app_name.capitalize()} permissions
"""
from rest_framework import permissions


class Is{model_name}Owner(permissions.BasePermission):
    """
    Permission to check if user owns the {model_name.lower()}
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
'''
    create_file(app_dir / 'permissions.py', permissions_content)
    
    # Create services directory if needed
    if config.get('has_services'):
        services_dir = app_dir / 'services'
        create_file(services_dir / '__init__.py', '')
        
        service_content = f'''"""
{app_name.capitalize()} business logic services
"""
from ..models import {model_name}


class {model_name}Service:
    """
    Service class for {model_name} business logic
    """
    
    @staticmethod
    def create_{model_name.lower()}(data):
        """
        Create a new {model_name.lower()}
        """
        return {model_name}.objects.create(**data)
    
    @staticmethod
    def get_{model_name.lower()}_by_id({model_name.lower()}_id):
        """
        Get {model_name.lower()} by ID
        """
        try:
            return {model_name}.objects.get(id={model_name.lower()}_id)
        except {model_name}.DoesNotExist:
            return None
'''
        create_file(services_dir / f'{app_name}_service.py', service_content)
    
    # Create filters.py if needed
    if config.get('has_filters'):
        filters_content = f'''"""
{app_name.capitalize()} filters
"""
import django_filters
from .models import {model_name}


class {model_name}Filter(django_filters.FilterSet):
    """
    Filter for {model_name}
    """
    class Meta:
        model = {model_name}
        fields = ['is_active']
'''
        create_file(app_dir / 'filters.py', filters_content)
    
    # Create signals.py if needed
    if config.get('has_signals'):
        signals_content = f'''"""
{app_name.capitalize()} signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import {model_name}


@receiver(post_save, sender={model_name})
def {model_name.lower()}_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for {model_name} post-save
    """
    if created:
        # Handle new {model_name.lower()} creation
        pass
'''
        create_file(app_dir / 'signals.py', signals_content)
    
    # Create webhooks.py if needed
    if config.get('has_webhooks'):
        webhooks_content = f'''"""
{app_name.capitalize()} webhooks
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhooks
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({{'error': 'Invalid payload'}}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({{'error': 'Invalid signature'}}, status=400)
    
    # Handle different event types
    if event['type'] == 'payment_intent.succeeded':
        # Handle successful payment
        pass
    
    return JsonResponse({{'status': 'success'}})
'''
        create_file(app_dir / 'webhooks.py', webhooks_content)
    
    # Create utils directory if needed
    if config.get('has_utils'):
        utils_dir = app_dir / 'utils'
        create_file(utils_dir / '__init__.py', '')
        
        utils_content = f'''"""
{app_name.capitalize()} utilities
"""
from datetime import datetime, timedelta


def get_date_range(start_date, end_date):
    """
    Get list of dates between start and end
    """
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates
'''
        create_file(utils_dir / 'time_utils.py', utils_content)
    
    # Create tests directory
    tests_dir = app_dir / 'tests'
    create_file(tests_dir / '__init__.py', '')


def main():
    """Main function to generate all app files"""
    print("Generating Django app files...")
    
    for app_name, config in APPS.items():
        print(f"\nGenerating files for {app_name}...")
        generate_app_files(app_name, config)
    
    print("\n✅ All app files generated successfully!")
    print("\nNext steps:")
    print("1. Review the generated files")
    print("2. Run: python manage.py makemigrations")
    print("3. Run: python manage.py migrate")


if __name__ == '__main__':
    main()
