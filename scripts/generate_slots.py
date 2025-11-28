"""
Generate time slots for shop schedules
"""
import os
import django
from datetime import datetime, timedelta, time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.schedules.models import ShopSchedule, TimeSlot
from apps.shops.models import Shop
from django.utils import timezone


def generate_slots_for_schedule(schedule, start_date, end_date):
    """
    Generate time slots for a schedule between start and end dates
    
    Args:
        schedule: ShopSchedule instance
        start_date: Start date
        end_date: End date
    """
    # Day name to weekday number mapping
    day_mapping = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6,
    }
    
    target_weekday = day_mapping[schedule.day_of_week]
    current_date = start_date
    
    while current_date <= end_date:
        if current_date.weekday() == target_weekday:
            # Generate slots for this day
            current_time = datetime.combine(current_date, schedule.start_time)
            end_time = datetime.combine(current_date, schedule.end_time)
            
            while current_time < end_time:
                slot_end = current_time + timedelta(minutes=schedule.slot_duration_minutes)
                
                if slot_end <= end_time:
                    # Create time slot
                    TimeSlot.objects.get_or_create(
                        schedule=schedule,
                        start_datetime=timezone.make_aware(current_time),
                        defaults={
                            'end_datetime': timezone.make_aware(slot_end),
                            'status': 'available',
                        }
                    )
                
                current_time = slot_end
        
        current_date += timedelta(days=1)


def generate_slots_for_shop(shop_id, days_ahead=30):
    """
    Generate time slots for a shop for the next N days
    
    Args:
        shop_id: Shop ID
        days_ahead: Number of days to generate slots for
    """
    try:
        shop = Shop.objects.get(id=shop_id)
        schedules = ShopSchedule.objects.filter(shop=shop, is_active=True)
        
        if not schedules.exists():
            print(f"No active schedules found for shop: {shop.name}")
            return
        
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days_ahead)
        
        print(f"Generating slots for {shop.name} from {start_date} to {end_date}")
        
        for schedule in schedules:
            print(f"  Processing {schedule.day_of_week}...")
            generate_slots_for_schedule(schedule, start_date, end_date)
        
        print(f"✅ Slots generated successfully for {shop.name}")
        
    except Shop.DoesNotExist:
        print(f"❌ Shop with ID {shop_id} not found")
    except Exception as e:
        print(f"❌ Error generating slots: {str(e)}")
        import traceback
        traceback.print_exc()


def generate_slots_for_all_shops(days_ahead=30):
    """
    Generate time slots for all active shops
    
    Args:
        days_ahead: Number of days to generate slots for
    """
    shops = Shop.objects.filter(is_active=True)
    
    if not shops.exists():
        print("No active shops found")
        return
    
    print(f"Generating slots for {shops.count()} shops...")
    
    for shop in shops:
        generate_slots_for_shop(shop.id, days_ahead)
    
    print("\n✅ All slots generated successfully!")


def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1:
        shop_id = sys.argv[1]
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        generate_slots_for_shop(shop_id, days)
    else:
        generate_slots_for_all_shops()


if __name__ == '__main__':
    main()
