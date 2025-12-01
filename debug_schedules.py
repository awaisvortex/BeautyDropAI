import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.schedules.models import ShopSchedule
from apps.shops.models import Shop

shop_id = '2378bcde-cf7b-49ca-8cb3-fcf5ba986e24'

print(f"Checking schedules for shop: {shop_id}")

try:
    shop = Shop.objects.get(id=shop_id)
    print(f"Shop found: {shop.name}")
    
    schedules = ShopSchedule.objects.filter(shop=shop)
    print(f"Found {schedules.count()} schedules:")
    
    for s in schedules:
        print(f"- Day: '{s.day_of_week}' (Active: {s.is_active})")
        
except Shop.DoesNotExist:
    print("Shop not found!")
except Exception as e:
    print(f"Error: {e}")
