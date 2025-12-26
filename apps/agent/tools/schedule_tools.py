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
    Supports natural language dates like 'tomorrow', 'tuesday', 'next monday'.
    Can also filter by specific staff member availability.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop"
                },
                "shop_name": {
                    "type": "string",
                    "description": "Alternative: Shop name if UUID not available"
                },
                "date": {
                    "type": "string",
                    "description": "Date to check - can be YYYY-MM-DD or natural language like 'tomorrow', 'tuesday', 'next monday'"
                },
                "service_id": {
                    "type": "string",
                    "description": "Optional: Service ID to check duration-specific availability"
                },
                "staff_id": {
                    "type": "string",
                    "description": "Optional: Staff member ID to check their specific availability"
                }
            },
            "required": ["date"]
        }
    
    def _parse_natural_date(self, date_str: str) -> date:
        """Parse natural language date strings."""
        date_str = date_str.lower().strip()
        today = timezone.now().date()
        
        # Handle standard format first
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        
        # Natural language mappings
        if date_str in ['today', 'now']:
            return today
        elif date_str in ['tomorrow', 'tmrw']:
            return today + timedelta(days=1)
        elif date_str in ['yesterday']:
            return today - timedelta(days=1)
        
        # Day of week
        weekdays = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }
        
        # Check for "next <weekday>" or just "<weekday>"
        for day_name, day_num in weekdays.items():
            if day_name in date_str:
                current_weekday = today.weekday()
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0:  # Same day means next week if "next" specified
                    if 'next' in date_str:
                        days_ahead = 7
                return today + timedelta(days=days_ahead)
        
        # Default to today if unparseable
        raise ValueError(f"Cannot parse date: {date_str}")
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Service
        from apps.staff.models import StaffMember
        from apps.schedules.models import Holiday
        from apps.schedules.services.availability import AvailabilityService
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get shop by ID or name
            shop_id = kwargs.get('shop_id')
            shop_name = kwargs.get('shop_name')
            
            if shop_id:
                try:
                    shop = Shop.objects.get(id=shop_id, is_active=True)
                except (Shop.DoesNotExist, Exception):
                    shop = Shop.objects.filter(name__icontains=shop_id, is_active=True).first()
            elif shop_name:
                shop = Shop.objects.filter(name__icontains=shop_name, is_active=True).first()
            else:
                return {"success": False, "error": "Please provide shop_id or shop_name"}
            
            if not shop:
                return {"success": False, "error": "Shop not found"}
            
            # Parse date
            try:
                check_date = self._parse_natural_date(kwargs['date'])
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
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
                    "shop_id": str(shop.id),
                    "date": check_date.isoformat(),
                    "is_holiday": True,
                    "holiday_name": holiday.name or "Closed",
                    "available_slots": [],
                    "message": f"{shop.name} is closed on {check_date.strftime('%B %d, %Y')}"
                }
            
            # Get service duration
            service_duration = 30  # default
            service = None
            service_id_or_name = kwargs.get('service_id')
            
            if service_id_or_name:
                # Try as UUID first
                try:
                    from uuid import UUID
                    UUID(str(service_id_or_name))
                    service = Service.objects.get(id=service_id_or_name, shop=shop, is_active=True)
                except (ValueError, Service.DoesNotExist):
                    # Try as name
                    service = Service.objects.filter(
                        shop=shop, 
                        name__icontains=service_id_or_name, 
                        is_active=True
                    ).first()
            else:
                # If no service specified, get first active service
                service = Service.objects.filter(shop=shop, is_active=True).first()
            
            if not service:
                return {
                    "success": False, 
                    "error": "Please specify a service. Use get_shop_services to see available services."
                }
            
            # Get available slots using AvailabilityService with correct API
            availability_service = AvailabilityService(
                service_id=service.id,
                target_date=check_date
            )
            raw_slots = availability_service.get_available_slots()
            
            # Filter by staff availability if specified
            staff_name = None
            if kwargs.get('staff_id'):
                try:
                    staff = StaffMember.objects.get(id=kwargs['staff_id'], shop=shop, is_active=True)
                    staff_name = staff.name
                    # Filter raw_slots to only include slots where this staff is available
                    raw_slots = [slot for slot in raw_slots if staff.id in slot.available_staff_ids]
                    logger.info(f"Filtering slots for staff: {staff.name}")
                except StaffMember.DoesNotExist:
                    pass
            
            # Get available staff for the service
            staff_members = StaffMember.objects.filter(
                shop=shop,
                is_active=True,
                services=service
            )
            staff_map = {s.id: s.name for s in staff_members}
            available_staff = [{"id": str(s.id), "name": s.name} for s in staff_members]
            
            # Format slots (raw_slots is list of AvailableSlot dataclass)
            formatted_slots = []
            for slot in raw_slots[:20]:  # Limit to 20 slots
                slot_data = {
                    "start_time": slot.start_time.strftime('%I:%M %p'),
                    "end_time": slot.end_time.strftime('%I:%M %p'),
                    "start_time_24h": slot.start_time.strftime('%H:%M'),
                }
                # Add available staff names for this slot
                if slot.available_staff_ids:
                    slot_data["available_staff"] = [
                        staff_map.get(sid, "Staff") 
                        for sid in slot.available_staff_ids 
                        if sid in staff_map
                    ]
                formatted_slots.append(slot_data)
            
            return {
                "success": True,
                "shop": shop.name,
                "shop_id": str(shop.id),
                "service": service.name,
                "service_id": str(service.id),
                "service_duration_minutes": service.duration_minutes,
                "date": check_date.isoformat(),
                "formatted_date": check_date.strftime("%A, %B %d, %Y"),
                "is_holiday": False,
                "slot_count": len(raw_slots),
                "available_slots": formatted_slots,
                "available_staff": available_staff,
                "filtered_by_staff": staff_name
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopHoursTool(BaseTool):
    """Get shop operating hours."""
    
    name = "get_shop_hours"
    description = """
    Get the weekly operating hours for a shop.
    Shows opening and closing times for each day.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
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
                    "close": schedule.end_time.strftime('%I:%M %p')
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
    allowed_roles = ["customer", "client", "staff", "guest"]
    
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
