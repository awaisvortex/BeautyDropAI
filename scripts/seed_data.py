"""
Seed database with sample data for development
"""
import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.authentication.models import User
from apps.clients.models import Client
from apps.customers.models import Customer
from apps.shops.models import Shop
from apps.services.models import Service
from apps.schedules.models import ShopSchedule
from django.utils import timezone


def create_sample_users():
    """Create sample users"""
    print("Creating sample users...")
    
    # Create client user
    client_user, created = User.objects.get_or_create(
        email='client@example.com',
        defaults={
            'clerk_user_id': 'clerk_client_123',
            'first_name': 'John',
            'last_name': 'Salon Owner',
            'role': 'client',
            'is_active': True,
        }
    )
    
    # Create customer user
    customer_user, created = User.objects.get_or_create(
        email='customer@example.com',
        defaults={
            'clerk_user_id': 'clerk_customer_123',
            'first_name': 'Jane',
            'last_name': 'Customer',
            'role': 'customer',
            'is_active': True,
        }
    )
    
    return client_user, customer_user


def create_sample_profiles(client_user, customer_user):
    """Create sample client and customer profiles"""
    print("Creating sample profiles...")
    
    # Create client profile
    client, created = Client.objects.get_or_create(
        user=client_user,
        defaults={
            'business_name': 'Luxury Salon & Spa',
            'phone': '+1234567890',
            'business_address': '123 Main St, New York, NY 10001',
            'max_shops': 3,
        }
    )
    
    # Create customer profile
    customer, created = Customer.objects.get_or_create(
        user=customer_user,
        defaults={
            'phone': '+1987654321',
        }
    )
    
    return client, customer


def create_sample_shops(client):
    """Create sample shops"""
    print("Creating sample shops...")
    
    shop, created = Shop.objects.get_or_create(
        client=client,
        name='Downtown Luxury Salon',
        defaults={
            'description': 'Premium salon services in the heart of downtown',
            'address': '123 Main St',
            'city': 'New York',
            'state': 'NY',
            'postal_code': '10001',
            'phone': '+1234567890',
            'email': 'info@luxurysalon.com',
            'is_active': True,
        }
    )
    
    return shop


def create_sample_services(shop):
    """Create sample services"""
    print("Creating sample services...")
    
    services_data = [
        {
            'name': 'Haircut',
            'description': 'Professional haircut and styling',
            'price': Decimal('50.00'),
            'duration_minutes': 60,
            'category': 'Hair',
        },
        {
            'name': 'Hair Coloring',
            'description': 'Full hair coloring service',
            'price': Decimal('120.00'),
            'duration_minutes': 120,
            'category': 'Hair',
        },
        {
            'name': 'Manicure',
            'description': 'Classic manicure',
            'price': Decimal('30.00'),
            'duration_minutes': 45,
            'category': 'Nails',
        },
        {
            'name': 'Pedicure',
            'description': 'Relaxing pedicure',
            'price': Decimal('40.00'),
            'duration_minutes': 60,
            'category': 'Nails',
        },
    ]
    
    for service_data in services_data:
        Service.objects.get_or_create(
            shop=shop,
            name=service_data['name'],
            defaults=service_data
        )


def create_sample_schedules(shop):
    """Create sample schedules"""
    print("Creating sample schedules...")
    
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    
    for day in weekdays:
        ShopSchedule.objects.get_or_create(
            shop=shop,
            day_of_week=day,
            defaults={
                'start_time': '09:00',
                'end_time': '18:00',
                'slot_duration_minutes': 30,
                'is_active': True,
            }
        )


def main():
    """Main seeding function"""
    print("Starting database seeding...")
    
    try:
        client_user, customer_user = create_sample_users()
        client, customer = create_sample_profiles(client_user, customer_user)
        shop = create_sample_shops(client)
        create_sample_services(shop)
        create_sample_schedules(shop)
        
        print("\n✅ Database seeded successfully!")
        print(f"Client: {client_user.email}")
        print(f"Customer: {customer_user.email}")
        print(f"Shop: {shop.name}")
        
    except Exception as e:
        print(f"\n❌ Error seeding database: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
