"""
Booking-related tools for the AI agent.
"""
from datetime import datetime
from typing import Any, Dict
from django.utils import timezone
from .base import BaseTool


class GetMyBookingsTool(BaseTool):
    """Get customer's or staff's bookings."""
    
    name = "get_my_bookings"
    description = """
    Get the user's bookings. For customers, shows their appointments.
    For staff, shows their assigned bookings.
    Can filter by status and time period.
    Always list ALL bookings returned in your response.
    If there are more than 10 bookings, mention the total count and suggest filtering by status or date.
    """
    allowed_roles = ["customer", "staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "confirmed", "completed", "cancelled", "all"],
                    "description": "Filter by booking status. Default: all"
                },
                "time_filter": {
                    "type": "string",
                    "enum": ["upcoming", "past", "today", "all"],
                    "description": "Filter by time: upcoming, past, today, or all. Default: upcoming"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of bookings to return. Default: 10, Max: 20"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.staff.models import StaffMember
        
        try:
            status = kwargs.get('status', 'all')
            time_filter = kwargs.get('time_filter', 'upcoming')
            limit = min(kwargs.get('limit', 10), 20)
            
            if role == 'customer':
                customer = Customer.objects.get(user=user)
                bookings = Booking.objects.filter(customer=customer)
            elif role == 'staff':
                staff = StaffMember.objects.get(user=user)
                bookings = Booking.objects.filter(staff_member=staff)
            else:
                return {"success": False, "error": "Invalid role for this tool"}
            
            bookings = bookings.select_related('shop', 'service', 'staff_member', 'customer__user')
            
            # Apply status filter
            if status != 'all':
                bookings = bookings.filter(status=status)
            
            # Apply time filter
            now = timezone.now()
            today = now.date()
            
            if time_filter == 'upcoming':
                bookings = bookings.filter(booking_datetime__gte=now)
            elif time_filter == 'past':
                bookings = bookings.filter(booking_datetime__lt=now)
            elif time_filter == 'today':
                bookings = bookings.filter(booking_datetime__date=today)
            
            # Get total count before limiting
            total_count = bookings.count()
            
            bookings = bookings.order_by('booking_datetime')[:limit]
            
            booking_list = []
            for b in bookings:
                booking_data = {
                    "booking_id": str(b.id),
                    "shop": b.shop.name,
                    "shop_id": str(b.shop.id),
                    "service": b.service.name,
                    "datetime": b.booking_datetime.isoformat(),
                    "formatted_datetime": b.booking_datetime.strftime("%B %d, %Y at %I:%M %p"),
                    "formatted_time": b.booking_datetime.strftime("%I:%M %p"),
                    "formatted_date": b.booking_datetime.strftime("%B %d, %Y"),
                    "price": float(b.total_price),
                    "status": b.status,
                    "staff": b.staff_member.name if b.staff_member else None
                }
                
                # Include customer info for staff
                if role == 'staff' and b.customer:
                    booking_data["customer_name"] = b.customer.user.full_name
                    booking_data["customer_email"] = b.customer.user.email
                
                booking_list.append(booking_data)
            
            return {
                "success": True,
                "total_count": total_count,
                "showing": len(booking_list),
                "has_more": total_count > limit,
                "filter_applied": {
                    "status": status,
                    "time_filter": time_filter
                },
                "bookings": booking_list,
                "message": f"Found {total_count} booking(s)." if total_count > 0 else "No bookings found matching your criteria."
            }
            
        except (Customer.DoesNotExist, StaffMember.DoesNotExist):
            return {"success": False, "error": "User profile not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CreateBookingTool(BaseTool):
    """Create a new booking."""
    
    name = "create_booking"
    description = """
    Create a new booking/appointment for the customer at a shop.
    Supports shop names and service names in addition to UUIDs.
    Supports natural language datetime like '2pm tomorrow' or 'tuesday at 14:00'.
    If staff_member_id is not provided, will auto-assign first available staff.
    IMPORTANT: Always check availability first using get_available_slots.
    """
    allowed_roles = ["customer"]
    
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
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service to book"
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative: Service name (e.g., 'Haircut')"
                },
                "booking_datetime": {
                    "type": "string",
                    "description": "Booking date and time - can be ISO format (2024-01-15T10:00:00) or natural language like 'tuesday at 2pm'"
                },
                "staff_member_id": {
                    "type": "string",
                    "description": "Optional: UUID of preferred staff member. If not provided, first available staff will be assigned."
                },
                "staff_name": {
                    "type": "string",
                    "description": "Optional: Preferred staff member name"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional: Special notes or requests for the booking"
                }
            },
            "required": ["booking_datetime"]
        }
    
    def _parse_booking_datetime(self, dt_str: str) -> datetime:
        """Parse booking datetime from various formats."""
        from datetime import timedelta
        
        dt_str = dt_str.strip()
        
        # Try ISO format first
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except ValueError:
            pass
        
        # Try to parse natural language
        today = timezone.now().date()
        current_time = timezone.now()
        
        # Extract time component (look for patterns like "2pm", "14:00", "2:30 pm")
        import re
        time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
        time_match = re.search(time_pattern, dt_str.lower())
        
        if not time_match:
            raise ValueError(f"Cannot parse time from: {dt_str}")
        
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        am_pm = time_match.group(3)
        
        if am_pm == 'pm' and hour < 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        
        # Extract date component
        dt_lower = dt_str.lower()
        
        if 'today' in dt_lower:
            target_date = today
        elif 'tomorrow' in dt_lower:
            target_date = today + timedelta(days=1)
        else:
            # Check for weekday
            weekdays = {
                'monday': 0, 'mon': 0,
                'tuesday': 1, 'tue': 1, 'tues': 1,
                'wednesday': 2, 'wed': 2,
                'thursday': 3, 'thu': 3, 'thur': 3,
                'friday': 4, 'fri': 4,
                'saturday': 5, 'sat': 5,
                'sunday': 6, 'sun': 6
            }
            
            target_date = None
            for day_name, day_num in weekdays.items():
                if day_name in dt_lower:
                    current_weekday = today.weekday()
                    days_ahead = (day_num - current_weekday) % 7
                    if days_ahead == 0:
                        if 'next' in dt_lower:
                            days_ahead = 7
                    target_date = today + timedelta(days=days_ahead)
                    break
            
            if not target_date:
                # Default to today if no date specified
                target_date = today
        
        # Combine date and time
        booking_dt = timezone.make_aware(
            datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
        )
        
        return booking_dt
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.shops.models import Shop
        from apps.services.models import Service
        from apps.staff.models import StaffMember
        from apps.schedules.services.availability import AvailabilityService
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"CreateBookingTool executing for user: {user.email if user else 'None'}")
            logger.info(f"Arguments received: {kwargs}")

            if not user or not user.is_authenticated:
                return {"success": False, "error": "User must be logged in to create a booking"}

            # Get or create customer profile
            customer, created = Customer.objects.get_or_create(user=user)
            if created:
                logger.info(f"Created missing Customer profile for {user.email} during booking")
            
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
            
            # Get service by ID or name
            service_id = kwargs.get('service_id')
            service_name = kwargs.get('service_name')
            
            if service_id:
                try:
                    service = Service.objects.get(id=service_id, shop=shop, is_active=True)
                except (Service.DoesNotExist, Exception):
                    service = Service.objects.filter(name__icontains=service_id, shop=shop, is_active=True).first()
            elif service_name:
                service = Service.objects.filter(name__icontains=service_name, shop=shop, is_active=True).first()
            else:
                return {"success": False, "error": "Please provide service_id or service_name"}
            
            if not service:
                return {"success": False, "error": f"Service not found at {shop.name}"}
            
            # Parse datetime
            try:
                booking_dt = self._parse_booking_datetime(kwargs['booking_datetime'])
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
            # Check if in the past
            if booking_dt < timezone.now():
                return {"success": False, "error": "Cannot book in the past"}
            
            # Check availability using AvailabilityService
            availability_service = AvailabilityService(
                service_id=service.id,
                target_date=booking_dt.date()
            )
            available_slots = availability_service.get_available_slots()
            
            # Verify the requested time is available
            slot_time = booking_dt.time()
            slot_available = any(
                slot.start_time.time() == slot_time
                for slot in available_slots
            )
            
            if not slot_available:
                # Suggest alternative times
                suggestions = [s.start_time.strftime('%I:%M %p') for s in available_slots[:5]]
                suggestion_text = ", ".join(suggestions) if suggestions else "No slots available"
                
                return {
                    "success": False,
                    "error": f"The requested time slot ({booking_dt.strftime('%I:%M %p')}) is not available.",
                    "available_times": suggestion_text,
                    "message": f"Available times on {booking_dt.strftime('%B %d')}: {suggestion_text}"
                }
            
            # Get staff member if specified, otherwise auto-assign
            staff_member = None
            staff_member_id = kwargs.get('staff_member_id')
            staff_name = kwargs.get('staff_name')
            
            if staff_member_id:
                try:
                    staff_member = StaffMember.objects.get(id=staff_member_id, shop=shop, is_active=True)
                except StaffMember.DoesNotExist:
                    pass
            elif staff_name:
                staff_member = StaffMember.objects.filter(
                    name__icontains=staff_name, shop=shop, is_active=True
                ).first()
            
            # Auto-assign first available staff if not specified
            if not staff_member:
                staff_for_service = StaffMember.objects.filter(
                    shop=shop, is_active=True, services=service
                ).first()
                if staff_for_service:
                    staff_member = staff_for_service
                    logger.info(f"Auto-assigned staff: {staff_member.name}")
            
            # Create the booking
            booking = Booking.objects.create(
                customer=customer,
                shop=shop,
                service=service,
                staff_member=staff_member,
                booking_datetime=booking_dt,
                total_price=service.price,
                notes=kwargs.get('notes', ''),
                status='pending'
            )
            
            return {
                "success": True,
                "message": f"Booking confirmed for {service.name} at {shop.name}",
                "booking": {
                    "booking_id": str(booking.id),
                    "shop": shop.name,
                    "shop_id": str(shop.id),
                    "service": service.name,
                    "service_id": str(service.id),
                    "datetime": booking_dt.isoformat(),
                    "formatted_datetime": booking_dt.strftime("%B %d, %Y at %I:%M %p"),
                    "price": float(service.price),
                    "status": booking.status,
                    "staff": staff_member.name if staff_member else "To be assigned",
                    "staff_id": str(staff_member.id) if staff_member else None
                }
            }
            
        except Customer.DoesNotExist:
            return {"success": False, "error": "Customer profile not found"}
        except Exception as e:
            logger.error(f"Create booking error: {e}")
            return {"success": False, "error": str(e)}


class RescheduleMyBookingTool(BaseTool):
    """Reschedule a customer's own booking."""
    
    name = "reschedule_my_booking"
    description = """
    Reschedule your own booking to a new date and time.
    Checks availability before rescheduling.
    Use when customer asks to change their appointment time.
    """
    allowed_roles = ["customer"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID of the booking to reschedule"
                },
                "new_datetime": {
                    "type": "string",
                    "description": "New date and time (e.g., 'tomorrow at 2pm', '2024-12-28 14:00')"
                }
            },
            "required": ["booking_id", "new_datetime"]
        }
    
    def _parse_datetime(self, dt_str: str):
        """Parse datetime from various formats."""
        from datetime import timedelta
        import re
        
        dt_str = dt_str.strip()
        
        # Try ISO format first
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except ValueError:
            pass
        
        today = timezone.now().date()
        
        # Extract time
        time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
        time_match = re.search(time_pattern, dt_str.lower())
        
        if not time_match:
            raise ValueError(f"Cannot parse time from: {dt_str}")
        
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        am_pm = time_match.group(3)
        
        if am_pm == 'pm' and hour < 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        
        # Extract date
        dt_lower = dt_str.lower()
        
        if 'today' in dt_lower:
            target_date = today
        elif 'tomorrow' in dt_lower:
            target_date = today + timedelta(days=1)
        else:
            weekdays = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            target_date = None
            for day_name, day_num in weekdays.items():
                if day_name in dt_lower:
                    current_weekday = today.weekday()
                    days_ahead = (day_num - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = today + timedelta(days=days_ahead)
                    break
            
            if not target_date:
                target_date = today
        
        return timezone.make_aware(
            datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
        )
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.schedules.services.availability import AvailabilityService
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if not user or not user.is_authenticated:
                return {"success": False, "error": "User must be logged in"}

            customer = Customer.objects.get(user=user)
            
            booking = Booking.objects.select_related('shop', 'service').get(
                id=kwargs['booking_id']
            )
            
            # Verify it's the customer's booking
            if booking.customer != customer:
                return {"success": False, "error": "This is not your booking"}
            
            if booking.status == 'cancelled':
                return {"success": False, "error": "Cannot reschedule a cancelled booking"}
            if booking.status == 'completed':
                return {"success": False, "error": "Cannot reschedule a completed booking"}
            
            # Parse new datetime
            try:
                new_dt = self._parse_datetime(kwargs['new_datetime'])
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
            if new_dt < timezone.now():
                return {"success": False, "error": "Cannot reschedule to a past time"}
            
            # Check availability
            availability_service = AvailabilityService(
                service_id=booking.service.id,
                target_date=new_dt.date()
            )
            available_slots = availability_service.get_available_slots()
            
            slot_time = new_dt.time()
            slot_available = any(
                slot.start_time.time() == slot_time
                for slot in available_slots
            )
            
            if not slot_available:
                suggestions = [s.start_time.strftime('%I:%M %p') for s in available_slots[:5]]
                return {
                    "success": False,
                    "error": f"The requested time ({new_dt.strftime('%I:%M %p')}) is not available.",
                    "available_times": suggestions,
                    "message": f"Available times on {new_dt.strftime('%B %d')}: {', '.join(suggestions) if suggestions else 'None'}"
                }
            
            # Update booking
            old_datetime = booking.booking_datetime
            booking.booking_datetime = new_dt
            booking.save()
            
            logger.info(f"Customer rescheduled booking {booking.id} from {old_datetime} to {new_dt}")
            
            return {
                "success": True,
                "message": f"Your appointment has been rescheduled from {old_datetime.strftime('%B %d at %I:%M %p')} to {new_dt.strftime('%B %d at %I:%M %p')}",
                "booking": {
                    "booking_id": str(booking.id),
                    "service": booking.service.name,
                    "shop": booking.shop.name,
                    "old_datetime": old_datetime.isoformat(),
                    "new_datetime": new_dt.isoformat(),
                    "formatted_new_datetime": new_dt.strftime("%B %d, %Y at %I:%M %p"),
                    "staff": booking.staff_member.name if booking.staff_member else "To be assigned"
                }
            }
            
        except Booking.DoesNotExist:
            return {"success": False, "error": "Booking not found"}
        except Customer.DoesNotExist:
            return {"success": False, "error": "Customer profile not found"}
        except Exception as e:
            logger.error(f"reschedule_my_booking error: {e}")
            return {"success": False, "error": str(e)}


class CancelBookingTool(BaseTool):
    """Cancel a booking."""
    
    
    name = "cancel_booking"
    description = """
    Cancel an existing booking. For customers, cancels their own booking.
    For shop owners, can cancel any booking at their shop.
    Requires booking_id.
    """
    allowed_roles = ["customer", "client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID of the booking to cancel"
                },
                "cancellation_reason": {
                    "type": "string",
                    "description": "Optional: Reason for cancellation"
                }
            },
            "required": ["booking_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.clients.models import Client
        
        try:
            booking_id = kwargs['booking_id']
            booking = Booking.objects.select_related('shop', 'service').get(id=booking_id)
            
            if not user or not user.is_authenticated:
                return {"success": False, "error": "User must be logged in"}
            
            # Permission check
            if role == 'customer':
                customer = Customer.objects.get(user=user)
                if booking.customer != customer:
                    return {"success": False, "error": "You can only cancel your own bookings"}
                cancelled_by = 'customer'
            elif role == 'client':
                client = Client.objects.get(user=user)
                if booking.shop.client != client:
                    return {"success": False, "error": "You can only cancel bookings at your shop"}
                cancelled_by = 'owner'
            else:
                return {"success": False, "error": "You don't have permission to cancel bookings"}
            
            # Check if already cancelled
            if booking.status == 'cancelled':
                return {"success": False, "error": "This booking is already cancelled"}
            
            # Check if completed
            if booking.status == 'completed':
                return {"success": False, "error": "Cannot cancel a completed booking"}
            
            # Cancel the booking
            booking.status = 'cancelled'
            booking.cancellation_reason = kwargs.get('cancellation_reason', '')
            booking.cancelled_at = timezone.now()
            booking.cancelled_by = cancelled_by
            booking.save()
            
            return {
                "success": True,
                "message": f"Booking for {booking.service.name} at {booking.shop.name} has been cancelled.",
                "cancelled_booking": {
                    "booking_id": str(booking.id),
                    "shop": booking.shop.name,
                    "service": booking.service.name,
                    "original_datetime": booking.booking_datetime.isoformat()
                }
            }
            
        except Booking.DoesNotExist:
            return {"success": False, "error": "Booking not found"}
        except (Customer.DoesNotExist, Client.DoesNotExist):
            return {"success": False, "error": "User profile not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopBookingsTool(BaseTool):
    """Get bookings for a shop (owner only)."""
    
    name = "get_shop_bookings"
    description = """
    Get bookings for the shop owner's shop.
    Can filter by date, status, or staff member.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Filter by date (YYYY-MM-DD). Default: today"
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "confirmed", "completed", "cancelled", "all"],
                    "description": "Filter by status. Default: all"
                },
                "staff_id": {
                    "type": "string",
                    "description": "Optional: Filter by staff member ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum bookings to return. Default: 20"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.clients.models import Client
        
        try:
            client = Client.objects.get(user=user)
            shop = client.shops.filter(is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No active shop found"}
            
            bookings = Booking.objects.filter(shop=shop).select_related(
                'customer__user', 'service', 'staff_member'
            )
            
            # Date filter
            date_str = kwargs.get('date')
            if date_str:
                try:
                    filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    filter_date = timezone.now().date()
            else:
                filter_date = timezone.now().date()
            
            bookings = bookings.filter(booking_datetime__date=filter_date)
            
            # Status filter
            status = kwargs.get('status', 'all')
            if status != 'all':
                bookings = bookings.filter(status=status)
            
            # Staff filter
            if kwargs.get('staff_id'):
                bookings = bookings.filter(staff_member_id=kwargs['staff_id'])
            
            limit = min(kwargs.get('limit', 20), 50)
            bookings = bookings.order_by('booking_datetime')[:limit]
            
            booking_list = []
            for b in bookings:
                booking_list.append({
                    "booking_id": str(b.id),
                    "customer": b.customer.user.full_name,
                    "customer_email": b.customer.user.email,
                    "service": b.service.name,
                    "datetime": b.booking_datetime.isoformat(),
                    "time": b.booking_datetime.strftime("%I:%M %p"),
                    "price": float(b.total_price),
                    "status": b.status,
                    "staff": b.staff_member.name if b.staff_member else "Unassigned"
                })
            
            return {
                "success": True,
                "shop": shop.name,
                "date": filter_date.isoformat(),
                "count": len(booking_list),
                "bookings": booking_list
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ConfirmBookingTool(BaseTool):
    """Confirm a pending booking (owner only)."""
    
    name = "confirm_booking"
    description = """
    Confirm a pending booking. Only shop owners can confirm bookings.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID of the booking to confirm"
                }
            },
            "required": ["booking_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.clients.models import Client
        
        try:
            client = Client.objects.get(user=user)
            booking = Booking.objects.select_related('shop', 'service', 'customer__user').get(
                id=kwargs['booking_id']
            )
            
            if booking.shop.client != client:
                return {"success": False, "error": "This booking is not at your shop"}
            
            if booking.status != 'pending':
                return {"success": False, "error": f"Cannot confirm booking with status: {booking.status}"}
            
            booking.status = 'confirmed'
            booking.save(update_fields=['status', 'updated_at'])
            
            return {
                "success": True,
                "message": f"Booking confirmed for {booking.customer.user.full_name}",
                "booking": {
                    "booking_id": str(booking.id),
                    "customer": booking.customer.user.full_name,
                    "service": booking.service.name,
                    "datetime": booking.booking_datetime.strftime("%B %d at %I:%M %p"),
                    "status": "confirmed"
                }
            }
            
        except Booking.DoesNotExist:
            return {"success": False, "error": "Booking not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
