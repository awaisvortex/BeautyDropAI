"""
Staff-specific tools for the AI agent.
Includes tools for staff members to manage their daily work.
"""
from datetime import datetime, date, timedelta
from typing import Any, Dict
from django.utils import timezone
from .base import BaseTool


class CompleteBookingTool(BaseTool):
    """Mark a booking as completed."""
    
    name = "complete_booking"
    description = """
    Mark a booking/appointment as completed.
    Use this after a service has been provided to the customer.
    Only staff members can mark their own bookings as complete.
    Works for both service and deal bookings.
    """
    allowed_roles = ["staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "UUID of the booking to mark as complete"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional: Notes about the service provided"
                }
            },
            "required": ["booking_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.staff.models import StaffMember
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            staff = StaffMember.objects.get(user=user)
            
            booking = Booking.objects.select_related(
                'customer__user', 'service', 'deal', 'shop'
            ).get(id=kwargs['booking_id'])
            
            # For deal bookings (no staff_member), check shop ownership
            # For service bookings, verify it's the staff's booking
            if booking.is_deal_booking:
                if booking.shop != staff.shop:
                    return {"success": False, "error": "This booking is not at your shop"}
            else:
                if booking.staff_member != staff:
                    return {"success": False, "error": "This booking is not assigned to you"}
            
            # Check status
            if booking.status == 'completed':
                return {"success": False, "error": "This booking is already completed"}
            if booking.status == 'cancelled':
                return {"success": False, "error": "Cannot complete a cancelled booking"}
            
            # Update booking
            booking.status = 'completed'
            if kwargs.get('notes'):
                booking.notes = (booking.notes + "\n" if booking.notes else "") + f"Staff notes: {kwargs['notes']}"
            booking.save()
            
            # Get item name (service or deal)
            if booking.service:
                item_name = booking.service.name
                # Update service booking count
                booking.service.booking_count += 1
                booking.service.save(update_fields=['booking_count'])
            elif booking.deal:
                item_name = booking.deal.name
            else:
                item_name = "appointment"
            
            logger.info(f"Staff {staff.name} completed booking {booking.id}")
            
            return {
                "success": True,
                "message": f"Booking marked as completed! {item_name} for {booking.customer.user.full_name}",
                "booking": {
                    "id": str(booking.id),
                    "customer": booking.customer.user.full_name,
                    "item_name": item_name,
                    "is_deal_booking": booking.is_deal_booking,
                    "datetime": booking.booking_datetime.strftime("%B %d at %I:%M %p"),
                    "status": "completed"
                }
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff profile not found"}
        except Booking.DoesNotExist:
            return {"success": False, "error": "Booking not found"}
        except Exception as e:
            logger.error(f"complete_booking error: {e}")
            return {"success": False, "error": str(e)}


class GetMyScheduleTool(BaseTool):
    """Get staff's daily/weekly schedule."""
    
    name = "get_my_schedule"
    description = """
    Get your work schedule for a specific day or the week.
    Shows all your appointments organized by time.
    Use to see what appointments you have today, tomorrow, or any day.
    """
    allowed_roles = ["staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to view (YYYY-MM-DD or 'today', 'tomorrow', 'monday', etc.). Default: today"
                },
                "view": {
                    "type": "string",
                    "enum": ["day", "week"],
                    "description": "View single day or full week. Default: day"
                }
            }
        }
    
    def _parse_date(self, date_str: str) -> date:
        """Parse date from various formats."""
        date_str = date_str.strip().lower()
        today = timezone.now().date()
        
        if not date_str or date_str == 'today':
            return today
        if date_str == 'tomorrow':
            return today + timedelta(days=1)
        
        # Try YYYY-MM-DD
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        
        # Try weekday
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_num in weekdays.items():
            if day_name in date_str:
                current_weekday = today.weekday()
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0 and 'next' not in date_str:
                    pass  # Today
                elif 'next' in date_str:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)
        
        return today
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.staff.models import StaffMember
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            staff = StaffMember.objects.select_related('shop').get(user=user)
            
            target_date = self._parse_date(kwargs.get('date', 'today'))
            view = kwargs.get('view', 'day')
            
            if view == 'week':
                # Get start of week (Monday)
                start_date = target_date - timedelta(days=target_date.weekday())
                end_date = start_date + timedelta(days=6)
            else:
                start_date = target_date
                end_date = target_date
            
            # Get bookings for the date range (staff member's bookings)
            bookings = Booking.objects.filter(
                staff_member=staff,
                booking_datetime__date__gte=start_date,
                booking_datetime__date__lte=end_date,
                status__in=['pending', 'confirmed']
            ).select_related('customer__user', 'service', 'deal').order_by('booking_datetime')
            
            # Helper to format booking data
            def format_booking(b):
                if b.service:
                    item_name = b.service.name
                    duration = b.service.duration_minutes
                elif b.deal:
                    item_name = b.deal.name
                    duration = b.duration_minutes
                else:
                    item_name = "Appointment"
                    duration = b.duration_minutes
                
                return {
                    "id": str(b.id),
                    "time": b.booking_datetime.strftime("%I:%M %p"),
                    "customer": b.customer.user.full_name,
                    "item_name": item_name,
                    "is_deal_booking": b.is_deal_booking,
                    "duration": duration,
                    "status": b.status
                }
            
            if view == 'week':
                # Group by date
                schedule = {}
                for day_offset in range(7):
                    day = start_date + timedelta(days=day_offset)
                    day_bookings = [b for b in bookings if b.booking_datetime.date() == day]
                    schedule[day.strftime('%A, %B %d')] = [format_booking(b) for b in day_bookings]
                
                total = len(bookings)
                return {
                    "success": True,
                    "view": "week",
                    "week_start": start_date.isoformat(),
                    "week_end": end_date.isoformat(),
                    "total_appointments": total,
                    "schedule_by_day": schedule,
                    "message": f"You have {total} appointment(s) this week at {staff.shop.name}"
                }
            else:
                # Single day view
                booking_list = []
                for b in bookings:
                    data = format_booking(b)
                    data["customer_phone"] = getattr(b.customer, 'phone', None)
                    data["price"] = float(b.total_price)
                    data["notes"] = b.notes
                    booking_list.append(data)
                
                return {
                    "success": True,
                    "view": "day",
                    "date": target_date.isoformat(),
                    "formatted_date": target_date.strftime("%A, %B %d, %Y"),
                    "shop": staff.shop.name,
                    "total_appointments": len(booking_list),
                    "appointments": booking_list,
                    "message": f"You have {len(booking_list)} appointment(s) on {target_date.strftime('%B %d')}"
                }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff profile not found"}
        except Exception as e:
            logger.error(f"get_my_schedule error: {e}")
            return {"success": False, "error": str(e)}


class GetCustomerHistoryTool(BaseTool):
    """View a customer's past visits."""
    
    name = "get_customer_history"
    description = """
    View a customer's past booking history at the shop.
    Helps staff prepare by knowing customer's previous services.
    """
    allowed_roles = ["staff", "client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name to search for"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Alternative: Customer's email"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of past visits to show. Default: 5"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.customers.models import Customer
        from apps.staff.models import StaffMember
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get shop context
            if role == 'staff':
                staff = StaffMember.objects.select_related('shop').get(user=user)
                shop = staff.shop
            else:
                client = Client.objects.get(user=user)
                shop = client.shops.filter(is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            customer_name = kwargs.get('customer_name')
            customer_email = kwargs.get('customer_email')
            limit = min(kwargs.get('limit', 5), 20)
            
            if not customer_name and not customer_email:
                return {"success": False, "error": "Please provide customer name or email"}
            
            # Find customer
            if customer_email:
                customer = Customer.objects.filter(
                    user__email__iexact=customer_email
                ).first()
            else:
                customer = Customer.objects.filter(
                    user__full_name__icontains=customer_name
                ).first()
            
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            # Get booking history at this shop
            bookings = Booking.objects.filter(
                customer=customer,
                shop=shop,
                status='completed'
            ).select_related('service', 'deal', 'staff_member').order_by('-booking_datetime')[:limit]
            
            history = []
            for b in bookings:
                if b.service:
                    item_name = b.service.name
                elif b.deal:
                    item_name = b.deal.name
                else:
                    item_name = "Appointment"
                
                history.append({
                    "date": b.booking_datetime.strftime("%B %d, %Y"),
                    "item_name": item_name,
                    "is_deal_booking": b.is_deal_booking,
                    "price": float(b.total_price),
                    "staff": b.staff_member.name if b.staff_member else None,
                    "notes": b.notes if b.notes else None
                })
            
            # Get total visits and last visit
            total_visits = Booking.objects.filter(
                customer=customer, shop=shop, status='completed'
            ).count()
            
            return {
                "success": True,
                "customer": {
                    "name": customer.user.full_name,
                    "email": customer.user.email,
                    "total_visits": total_visits
                },
                "shop": shop.name,
                "recent_visits": history,
                "message": f"{customer.user.full_name} has visited {shop.name} {total_visits} time(s)"
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff profile not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"get_customer_history error: {e}")
            return {"success": False, "error": str(e)}


class GetMyServicesTool(BaseTool):
    """Get services the staff member can provide."""
    
    name = "get_my_services"
    description = """
    View the list of services you are assigned to provide.
    Shows which services you can be booked for.
    """
    allowed_roles = ["staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {}
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.staff.models import StaffMember
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            staff = StaffMember.objects.select_related('shop').prefetch_related(
                'services', 'staff_services'
            ).get(user=user)
            
            services = []
            for ss in staff.staff_services.select_related('service').all():
                service = ss.service
                if service.is_active:
                    services.append({
                        "id": str(service.id),
                        "name": service.name,
                        "price": float(service.price),
                        "duration_minutes": service.duration_minutes,
                        "category": service.category,
                        "is_primary": ss.is_primary
                    })
            
            return {
                "success": True,
                "staff_name": staff.name,
                "shop": staff.shop.name,
                "total_services": len(services),
                "services": services,
                "message": f"You provide {len(services)} service(s) at {staff.shop.name}"
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff profile not found"}
        except Exception as e:
            logger.error(f"get_my_services error: {e}")
            return {"success": False, "error": str(e)}


class GetTodaySummaryTool(BaseTool):
    """Get a summary of today's work."""
    
    name = "get_today_summary"
    description = """
    Get a summary of today's appointments and stats.
    Shows completed, upcoming, and pending appointments.
    """
    allowed_roles = ["staff"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {}
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.bookings.models import Booking
        from apps.staff.models import StaffMember
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            staff = StaffMember.objects.select_related('shop').get(user=user)
            today = timezone.now().date()
            now = timezone.now()
            
            # Get all today's bookings
            today_bookings = Booking.objects.filter(
                staff_member=staff,
                booking_datetime__date=today
            ).select_related('customer__user', 'service', 'deal')
            
            completed = []
            upcoming = []
            pending_confirm = []
            
            for b in today_bookings:
                # Get item name (service or deal)
                if b.service:
                    item_name = b.service.name
                elif b.deal:
                    item_name = b.deal.name
                else:
                    item_name = "Appointment"
                
                booking_data = {
                    "id": str(b.id),
                    "time": b.booking_datetime.strftime("%I:%M %p"),
                    "customer": b.customer.user.full_name,
                    "item_name": item_name,
                    "is_deal_booking": b.is_deal_booking
                }
                
                if b.status == 'completed':
                    completed.append(booking_data)
                elif b.status == 'cancelled':
                    pass  # Skip cancelled
                elif b.status == 'pending':
                    pending_confirm.append(booking_data)
                else:  # confirmed
                    if b.booking_datetime > now:
                        upcoming.append(booking_data)
                    else:
                        upcoming.append(booking_data)  # Past but not marked complete
            
            # Calculate earnings
            total_earned = sum(
                float(b.total_price) for b in today_bookings if b.status == 'completed'
            )
            
            return {
                "success": True,
                "date": today.strftime("%A, %B %d, %Y"),
                "shop": staff.shop.name,
                "summary": {
                    "completed": len(completed),
                    "upcoming": len(upcoming),
                    "pending_confirmation": len(pending_confirm),
                    "total_today": len(completed) + len(upcoming) + len(pending_confirm)
                },
                "earnings_today": total_earned,
                "completed_appointments": completed,
                "upcoming_appointments": upcoming,
                "pending_appointments": pending_confirm,
                "message": f"Today: {len(completed)} completed, {len(upcoming)} upcoming, ${total_earned:.2f} earned"
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff profile not found"}
        except Exception as e:
            logger.error(f"get_today_summary error: {e}")
            return {"success": False, "error": str(e)}
