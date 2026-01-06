"""
Deal-related tools for the AI agent.
Allows voice agents to work with deals/packages.
"""
from typing import Any, Dict
from datetime import datetime, timedelta, date
from django.utils import timezone
from .base import BaseTool


class GetShopDealsTool(BaseTool):
    """Get deals/packages offered by a shop."""
    
    name = "get_shop_deals"
    description = """
    Get all deals/packages offered by a shop.
    Deals are special bundles of services at a discounted price.
    Includes names, descriptions, prices, duration, and included items.
    Use this when customer asks about 'deals', 'packages', 'specials', or 'bundles'.
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
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Deal
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Try UUID first, then fall back to name search
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
            
            deals = Deal.objects.filter(shop=shop, is_active=True).order_by('price')
            
            if not deals.exists():
                return {
                    "success": True,
                    "shop": shop.name,
                    "deals": [],
                    "message": f"{shop.name} doesn't have any deals/packages available at the moment."
                }
            
            deal_list = [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "description": d.description,
                    "price": float(d.price),
                    "duration_minutes": d.duration_minutes,
                    "included_items": d.included_items,
                    "items_count": len(d.included_items) if d.included_items else 0
                }
                for d in deals
            ]
            
            logger.info(f"get_shop_deals found {len(deal_list)} deals for shop {shop.name}")
            
            return {
                "success": True,
                "shop": shop.name,
                "shop_id": str(shop.id),
                "count": len(deal_list),
                "deals": deal_list
            }
            
        except Exception as e:
            logger.error(f"get_shop_deals error: {e}")
            return {"success": False, "error": str(e)}


class GetDealSlotsTool(BaseTool):
    """Get available time slots for booking a deal."""
    
    name = "get_deal_slots"
    description = """
    Get available time slots for booking a deal/package.
    Deals don't require staff - just shop hours and capacity.
    Returns slots with 'slots_left' showing remaining capacity at each time.
    Use this before booking a deal to show available times.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "UUID of the deal to check availability for"
                },
                "date": {
                    "type": "string",
                    "description": "Date to check - can be YYYY-MM-DD or natural language like 'tomorrow', 'tuesday'"
                }
            },
            "required": ["deal_id", "date"]
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
        
        for day_name, day_num in weekdays.items():
            if day_name in date_str:
                current_weekday = today.weekday()
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0 and 'next' in date_str:
                    days_ahead = 7
                return today + timedelta(days=days_ahead)
        
        raise ValueError(f"Cannot parse date: {date_str}")
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.services.models import Deal
        from apps.schedules.models import ShopSchedule
        from apps.bookings.models import Booking
        import pytz
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            deal_id = kwargs.get('deal_id')
            date_str = kwargs.get('date', 'today')
            
            if not deal_id:
                return {"success": False, "error": "deal_id is required"}
            
            # Parse date
            try:
                target_date = self._parse_natural_date(date_str)
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
            # Get deal
            try:
                deal = Deal.objects.select_related('shop').get(id=deal_id, is_active=True)
            except Deal.DoesNotExist:
                return {"success": False, "error": "Deal not found or not active"}
            
            shop = deal.shop
            max_concurrent = shop.max_concurrent_deal_bookings
            
            # Get shop's timezone
            try:
                shop_tz = pytz.timezone(shop.timezone)
            except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                shop_tz = pytz.UTC
            
            # Get schedule for this day
            day_name = target_date.strftime('%A').lower()
            try:
                schedule = ShopSchedule.objects.get(shop=shop, day_of_week=day_name)
            except ShopSchedule.DoesNotExist:
                return {
                    "success": True,
                    "deal": deal.name,
                    "date": target_date.isoformat(),
                    "slots": [],
                    "message": f"{shop.name} has no schedule for {day_name.capitalize()}"
                }
            
            if not schedule.is_active or not schedule.start_time or not schedule.end_time:
                return {
                    "success": True,
                    "deal": deal.name,
                    "date": target_date.isoformat(),
                    "slots": [],
                    "message": f"{shop.name} is closed on {day_name.capitalize()}"
                }
            
            # Generate slots
            slot_duration = deal.duration_minutes
            slots = []
            
            # Get existing deal bookings for this date
            existing_bookings = Booking.objects.filter(
                shop=shop,
                deal__isnull=False,
                booking_datetime__date=target_date,
                status__in=['pending', 'confirmed']
            )
            
            current_time = datetime.combine(target_date, schedule.start_time)
            end_time = datetime.combine(target_date, schedule.end_time)
            
            # Localize to shop timezone
            current_time = shop_tz.localize(current_time)
            end_time = shop_tz.localize(end_time)
            
            now = timezone.now()
            buffer_time = now + timedelta(minutes=15)
            
            while current_time + timedelta(minutes=slot_duration) <= end_time:
                slot_end = current_time + timedelta(minutes=slot_duration)
                
                # Skip past slots
                if current_time < buffer_time:
                    current_time = current_time + timedelta(minutes=30)
                    continue
                
                # Count overlapping bookings
                overlapping = 0
                for booking in existing_bookings:
                    booking_end = booking.booking_datetime + timedelta(minutes=booking.duration_minutes)
                    if booking.booking_datetime < slot_end and booking_end > current_time:
                        overlapping += 1
                
                slots_left = max(0, max_concurrent - overlapping)
                
                slots.append({
                    "start_time": current_time.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M"),
                    "slots_left": slots_left,
                    "is_available": slots_left > 0
                })
                
                current_time = current_time + timedelta(minutes=30)
            
            available_count = sum(1 for s in slots if s['is_available'])
            
            logger.info(f"get_deal_slots found {available_count} available slots for deal {deal.name}")
            
            return {
                "success": True,
                "deal": deal.name,
                "deal_id": str(deal.id),
                "duration_minutes": deal.duration_minutes,
                "price": float(deal.price),
                "date": target_date.isoformat(),
                "shop_open": schedule.start_time.strftime("%H:%M"),
                "shop_close": schedule.end_time.strftime("%H:%M"),
                "max_concurrent": max_concurrent,
                "available_slots_count": available_count,
                "slots": slots
            }
            
        except Exception as e:
            logger.error(f"get_deal_slots error: {e}")
            return {"success": False, "error": str(e)}


class CreateDealBookingTool(BaseTool):
    """Book a deal/package for a customer."""
    
    name = "create_deal_booking"
    description = """
    Create a booking for a deal/package.
    Deals don't require staff assignment - just a time slot within shop hours.
    ALWAYS call get_deal_slots first to ensure the slot is available.
    Use this when customer wants to book a deal or package.
    """
    allowed_roles = ["customer", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "UUID of the deal to book"
                },
                "date": {
                    "type": "string",
                    "description": "Date for the booking - YYYY-MM-DD or natural language"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in HH:MM format (24-hour)"
                },
                "customer_name": {
                    "type": "string",
                    "description": "Required for guest bookings: Customer's name"
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Required for guest bookings: Customer's phone number"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes for the booking"
                }
            },
            "required": ["deal_id", "date", "start_time"]
        }
    
    def _parse_natural_date(self, date_str: str) -> date:
        """Parse natural language date strings."""
        date_str = date_str.lower().strip()
        today = timezone.now().date()
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        
        if date_str in ['today', 'now']:
            return today
        elif date_str in ['tomorrow', 'tmrw']:
            return today + timedelta(days=1)
        
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_num in weekdays.items():
            if day_name in date_str:
                current_weekday = today.weekday()
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0 and 'next' in date_str:
                    days_ahead = 7
                return today + timedelta(days=days_ahead)
        
        raise ValueError(f"Cannot parse date: {date_str}")
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.services.models import Deal
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        import pytz
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            deal_id = kwargs.get('deal_id')
            date_str = kwargs.get('date')
            start_time_str = kwargs.get('start_time')
            notes = kwargs.get('notes', '')
            
            if not all([deal_id, date_str, start_time_str]):
                return {"success": False, "error": "deal_id, date, and start_time are required"}
            
            # Parse date
            try:
                target_date = self._parse_natural_date(date_str)
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
            # Parse time
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
            except ValueError:
                return {"success": False, "error": "Invalid time format. Use HH:MM (e.g., 10:00)"}
            
            # Get deal
            try:
                deal = Deal.objects.select_related('shop').get(id=deal_id, is_active=True)
            except Deal.DoesNotExist:
                return {"success": False, "error": "Deal not found or not active"}
            
            shop = deal.shop
            max_concurrent = shop.max_concurrent_deal_bookings
            
            # Get shop's timezone
            try:
                shop_tz = pytz.timezone(shop.timezone)
            except:
                shop_tz = pytz.UTC
            
            # Create booking datetime
            booking_datetime = shop_tz.localize(datetime.combine(target_date, start_time))
            slot_end = booking_datetime + timedelta(minutes=deal.duration_minutes)
            
            # Check if in the past
            if booking_datetime < timezone.now() + timedelta(minutes=15):
                return {"success": False, "error": "Booking time must be at least 15 minutes from now"}
            
            # Check capacity
            existing_bookings = Booking.objects.filter(
                shop=shop,
                deal__isnull=False,
                status__in=['pending', 'confirmed'],
                booking_datetime__date=target_date
            )
            
            overlapping = 0
            for booking in existing_bookings:
                booking_end = booking.booking_datetime + timedelta(minutes=booking.duration_minutes)
                if booking.booking_datetime < slot_end and booking_end > booking_datetime:
                    overlapping += 1
            
            if overlapping >= max_concurrent:
                return {
                    "success": False,
                    "error": "No slots available at this time. Maximum capacity reached.",
                    "slots_left": 0
                }
            
            # Get or create customer
            if user and hasattr(user, 'customer_profile'):
                customer = user.customer_profile
            elif user:
                customer, _ = Customer.objects.get_or_create(user=user)
            else:
                # Guest booking - need customer info
                customer_name = kwargs.get('customer_name')
                customer_phone = kwargs.get('customer_phone')
                if not customer_name or not customer_phone:
                    return {
                        "success": False,
                        "error": "Guest bookings require customer_name and customer_phone"
                    }
                # Create a guest customer record
                from apps.authentication.models import User
                guest_user, _ = User.objects.get_or_create(
                    email=f"guest_{customer_phone.replace('+', '').replace(' ', '')}@beautydrop.guest",
                    defaults={
                        'full_name': customer_name,
                        'role': 'customer',
                        'phone_number': customer_phone
                    }
                )
                customer, _ = Customer.objects.get_or_create(user=guest_user)
            
            # Create booking
            booking = Booking.objects.create(
                customer=customer,
                shop=shop,
                service=None,
                deal=deal,
                time_slot=None,
                staff_member=None,
                booking_datetime=booking_datetime,
                duration_minutes=deal.duration_minutes,
                total_price=deal.price,
                notes=notes,
                status='pending'
            )
            
            logger.info(f"Created deal booking {booking.id} for deal {deal.name}")
            
            return {
                "success": True,
                "message": f"Successfully booked {deal.name} at {shop.name}!",
                "booking": {
                    "id": str(booking.id),
                    "deal_name": deal.name,
                    "shop_name": shop.name,
                    "date": target_date.isoformat(),
                    "time": start_time_str,
                    "duration_minutes": deal.duration_minutes,
                    "price": float(deal.price),
                    "included_items": deal.included_items,
                    "status": booking.status
                }
            }
            
        except Exception as e:
            logger.error(f"create_deal_booking error: {e}")
            return {"success": False, "error": str(e)}
