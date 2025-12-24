"""
Schedule and availability tools for the AI agent.
"""
from datetime import datetime, date, timedelta
from typing import Any, Dict
from django.utils import timezone
from .base import BaseTool


class GetAvailableSlotsTool(BaseTool):
    """Get available time slots."""
    
    name = "get_available_slots"
    description = """
    Get available time slots for booking at a shop on a specific date.
    ALWAYS use this before creating a booking to ensure the slot is available.
    """
    allowed_roles = ["customer", "client", "staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop"
                },
                "date": {
                    "type": "string",
                    "description": "Date to check (YYYY-MM-DD format)"
                },
                "service_id": {
                    "type": "string",
                    "description": "Optional: Service ID to check duration-specific availability"
                }
            },
            "required": ["shop_id", "date"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Service
        from apps.schedules.models import Holiday
        from apps.schedules.services.availability import AvailabilityService
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            
            try:
                check_date = datetime.strptime(kwargs['date'], '%Y-%m-%d').date()
            except ValueError:
                return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
            
            # Check if past date
            if check_date < timezone.now().date():
                return {"success": False, "error": "Cannot check availability for past dates"}
            
            # Check if holiday
            is_holiday = Holiday.objects.filter(shop=shop, date=check_date).exists()
            if is_holiday:
                holiday = Holiday.objects.get(shop=shop, date=check_date)
                return {
                    "success": True,
                    "shop": shop.name,
                    "date": check_date.isoformat(),
                    "is_holiday": True,
                    "holiday_name": holiday.name or "Closed",
                    "available_slots": [],
                    "message": f"{shop.name} is closed on {check_date.strftime('%B %d, %Y')}"
                }
            
            # Get service duration
            service_duration = 30  # default
            if kwargs.get('service_id'):
                try:
                    service = Service.objects.get(id=kwargs['service_id'], shop=shop)
                    service_duration = service.duration_minutes
                except Service.DoesNotExist:
                    pass
            
            # Get available slots
            availability_service = AvailabilityService(shop)
            slots = availability_service.get_available_slots(
                date=check_date,
                service_duration=service_duration
            )
            
            return {
                "success": True,
                "shop": shop.name,
                "date": check_date.isoformat(),
                "formatted_date": check_date.strftime("%A, %B %d, %Y"),
                "is_holiday": False,
                "slot_count": len(slots),
                "available_slots": [
                    {
                        "start_time": slot['start_time'].strftime('%I:%M %p'),
                        "end_time": slot['end_time'].strftime('%I:%M %p'),
                        "start_time_24h": slot['start_time'].strftime('%H:%M')
                    }
                    for slot in slots
                ]
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopHoursTool(BaseTool):
    """Get shop operating hours."""
    
    name = "get_shop_hours"
    description = """
    Get the weekly operating hours for a shop.
    Shows opening and closing times for each day.
    """
    allowed_roles = ["customer", "client", "staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop"
                }
            },
            "required": ["shop_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import ShopSchedule
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            schedules = ShopSchedule.objects.filter(shop=shop, is_active=True)
            
            # Build hours by day
            day_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            hours_map = {}
            
            for schedule in schedules:
                hours_map[schedule.day_of_week] = {
                    "open": schedule.start_time.strftime('%I:%M %p'),
                    "close": schedule.end_time.strftime('%I:%M %p'),
                    "slot_duration": schedule.slot_duration_minutes
                }
            
            weekly_hours = []
            for day in day_order:
                if day in hours_map:
                    weekly_hours.append({
                        "day": day.capitalize(),
                        "is_open": True,
                        **hours_map[day]
                    })
                else:
                    weekly_hours.append({
                        "day": day.capitalize(),
                        "is_open": False,
                        "open": None,
                        "close": None
                    })
            
            return {
                "success": True,
                "shop": shop.name,
                "timezone": shop.timezone,
                "weekly_hours": weekly_hours
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopHolidaysTool(BaseTool):
    """Get upcoming shop holidays."""
    
    name = "get_shop_holidays"
    description = """
    Get upcoming holidays/closure dates for a shop.
    Use to inform customers about days when the shop will be closed.
    """
    allowed_roles = ["customer", "client", "staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop"
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days to look ahead. Default: 30"
                }
            },
            "required": ["shop_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import Holiday
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            days_ahead = min(kwargs.get('days_ahead', 30), 90)
            
            today = date.today()
            end_date = today + timedelta(days=days_ahead)
            
            holidays = Holiday.objects.filter(
                shop=shop,
                date__gte=today,
                date__lte=end_date
            ).order_by('date')
            
            return {
                "success": True,
                "shop": shop.name,
                "holidays": [
                    {
                        "date": h.date.isoformat(),
                        "formatted_date": h.date.strftime("%A, %B %d, %Y"),
                        "name": h.name or "Closed"
                    }
                    for h in holidays
                ]
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
