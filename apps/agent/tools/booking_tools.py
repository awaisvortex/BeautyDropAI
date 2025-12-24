"""
Booking-related tools for the AI agent.
"""
from datetime import datetime
from typing import Any, Dict
from django.utils import timezone
from .base import BaseTool


class GetMyBookingsTool(BaseTool):
    """Get customer's bookings."""
    
    name = "get_my_bookings"
    description = """
    Get the user's bookings. For customers, shows their appointments.
    For staff, shows their assigned bookings.
    Can filter by status and time period.
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
                    "description": "Maximum number of bookings to return. Default: 10"
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
            
            bookings = bookings.select_related('shop', 'service', 'staff_member')
            
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
            
            bookings = bookings.order_by('booking_datetime')[:limit]
            
            booking_list = []
            for b in bookings:
                booking_list.append({
                    "booking_id": str(b.id),
                    "shop": b.shop.name,
                    "shop_id": str(b.shop.id),
                    "service": b.service.name,
                    "datetime": b.booking_datetime.isoformat(),
                    "formatted_datetime": b.booking_datetime.strftime("%B %d, %Y at %I:%M %p"),
                    "price": float(b.total_price),
                    "status": b.status,
                    "staff": b.staff_member.name if b.staff_member else None
                })
            
            return {
                "success": True,
                "count": len(booking_list),
                "bookings": booking_list
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
    Requires: shop_id, service_id, booking_datetime (ISO format).
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
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service to book"
                },
                "booking_datetime": {
                    "type": "string",
                    "description": "Booking date and time in ISO 8601 format (e.g., 2024-01-15T10:00:00)"
                },
                "staff_member_id": {
                    "type": "string",
                    "description": "Optional: UUID of preferred staff member"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional: Special notes or requests for the booking"
                }
            },
            "required": ["shop_id", "service_id", "booking_datetime"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.shops.models import Shop
        from apps.services.models import Service
        from apps.staff.models import StaffMember
        from apps.schedules.services.availability import AvailabilityService
        
        try:
            customer = Customer.objects.get(user=user)
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            service = Service.objects.get(id=kwargs['service_id'], shop=shop, is_active=True)
            
            # Parse datetime
            booking_dt_str = kwargs['booking_datetime']
            booking_dt = datetime.fromisoformat(booking_dt_str.replace('Z', '+00:00'))
            
            if timezone.is_naive(booking_dt):
                booking_dt = timezone.make_aware(booking_dt)
            
            # Check if in the past
            if booking_dt < timezone.now():
                return {"success": False, "error": "Cannot book in the past"}
            
            # Check availability
            availability_service = AvailabilityService(shop)
            available_slots = availability_service.get_available_slots(
                date=booking_dt.date(),
                service_duration=service.duration_minutes
            )
            
            # Verify the slot is available
            slot_time = booking_dt.time()
            slot_available = any(
                slot['start_time'] == slot_time
                for slot in available_slots
            )
            
            if not slot_available:
                return {
                    "success": False,
                    "error": "The requested time slot is not available. Please check availability and choose a different time."
                }
            
            # Get staff member if specified
            staff_member = None
            if kwargs.get('staff_member_id'):
                try:
                    staff_member = StaffMember.objects.get(
                        id=kwargs['staff_member_id'],
                        shop=shop,
                        is_active=True
                    )
                except StaffMember.DoesNotExist:
                    pass
            
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
                    "service": service.name,
                    "datetime": booking_dt.isoformat(),
                    "formatted_datetime": booking_dt.strftime("%B %d, %Y at %I:%M %p"),
                    "price": float(service.price),
                    "status": booking.status,
                    "staff": staff_member.name if staff_member else "To be assigned"
                }
            }
            
        except Customer.DoesNotExist:
            return {"success": False, "error": "Customer profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Service.DoesNotExist:
            return {"success": False, "error": "Service not found at this shop"}
        except ValueError as e:
            return {"success": False, "error": f"Invalid datetime format: {e}"}
        except Exception as e:
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
