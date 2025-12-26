"""
Management tools for shop owners (client role).
Includes tools for managing staff, holidays, services, and bookings.
"""
from datetime import datetime, date, timedelta
from typing import Any, Dict
from django.utils import timezone
from .base import BaseTool


class CreateHolidayTool(BaseTool):
    """Create a holiday/closure date for a shop."""
    
    name = "create_holiday"
    description = """
    Add a holiday or closure date for a shop.
    The shop will be closed on this date and no bookings can be made.
    Use for holidays like Christmas, Eid, or any shop closure.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop. If not provided, uses first active shop."
                },
                "date": {
                    "type": "string",
                    "description": "Date for the holiday (YYYY-MM-DD or natural language like 'december 25', 'next friday')"
                },
                "name": {
                    "type": "string",
                    "description": "Optional: Name of the holiday (e.g., 'Christmas', 'Eid', 'Shop Renovation')"
                }
            },
            "required": ["date"]
        }
    
    def _parse_date(self, date_str: str) -> date:
        """Parse date from various formats."""
        import re
        date_str = date_str.strip().lower()
        today = timezone.now().date()
        
        # Try YYYY-MM-DD format
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        
        # Try natural language
        if 'today' in date_str:
            return today
        if 'tomorrow' in date_str:
            return today + timedelta(days=1)
        
        # Try "month day" format (e.g., "december 25")
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        for month_name, month_num in months.items():
            if month_name in date_str:
                day_match = re.search(r'\d+', date_str)
                if day_match:
                    day = int(day_match.group())
                    year = today.year
                    # If the date has passed this year, use next year
                    target = date(year, month_num, day)
                    if target < today:
                        target = date(year + 1, month_num, day)
                    return target
        
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
                    days_ahead = 7
                if 'next' in date_str and days_ahead <= 7:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)
        
        raise ValueError(f"Cannot parse date: {date_str}")
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import Holiday
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            # Get shop
            shop_id = kwargs.get('shop_id')
            if shop_id:
                shop = Shop.objects.get(id=shop_id, client=client)
            else:
                shop = Shop.objects.filter(client=client, is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            # Parse date
            try:
                holiday_date = self._parse_date(kwargs['date'])
            except ValueError as e:
                return {"success": False, "error": str(e)}
            
            # Check if date is in the past
            if holiday_date < timezone.now().date():
                return {"success": False, "error": "Cannot create holiday for a past date"}
            
            # Check if holiday already exists
            if Holiday.objects.filter(shop=shop, date=holiday_date).exists():
                return {"success": False, "error": f"A holiday already exists for {holiday_date}"}
            
            # Create the holiday
            holiday = Holiday.objects.create(
                shop=shop,
                date=holiday_date,
                name=kwargs.get('name', '')
            )
            
            logger.info(f"Created holiday for {shop.name} on {holiday_date}")
            
            return {
                "success": True,
                "message": f"Holiday created for {shop.name} on {holiday_date.strftime('%B %d, %Y')}",
                "holiday": {
                    "id": str(holiday.id),
                    "shop": shop.name,
                    "date": holiday_date.isoformat(),
                    "formatted_date": holiday_date.strftime("%B %d, %Y"),
                    "name": holiday.name or "Shop Closed"
                }
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found or you don't own this shop"}
        except Exception as e:
            logger.error(f"create_holiday error: {e}")
            return {"success": False, "error": str(e)}


class DeleteHolidayTool(BaseTool):
    """Delete a holiday/closure date."""
    
    name = "delete_holiday"
    description = """
    Remove a holiday/closure date from a shop.
    The shop will be open on this date again.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "holiday_id": {
                    "type": "string",
                    "description": "UUID of the holiday to delete"
                },
                "date": {
                    "type": "string",
                    "description": "Alternative: Delete holiday by date (YYYY-MM-DD)"
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: Shop ID (required if using date instead of holiday_id)"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import Holiday
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            holiday_id = kwargs.get('holiday_id')
            date_str = kwargs.get('date')
            
            if holiday_id:
                holiday = Holiday.objects.select_related('shop').get(id=holiday_id)
                if holiday.shop.client != client:
                    return {"success": False, "error": "This holiday is not for your shop"}
            elif date_str:
                shop_id = kwargs.get('shop_id')
                if shop_id:
                    shop = Shop.objects.get(id=shop_id, client=client)
                else:
                    shop = Shop.objects.filter(client=client, is_active=True).first()
                
                if not shop:
                    return {"success": False, "error": "No shop found"}
                
                try:
                    holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
                
                holiday = Holiday.objects.get(shop=shop, date=holiday_date)
            else:
                return {"success": False, "error": "Please provide holiday_id or date"}
            
            shop_name = holiday.shop.name
            holiday_date = holiday.date
            holiday_name = holiday.name
            
            holiday.delete()
            
            logger.info(f"Deleted holiday for {shop_name} on {holiday_date}")
            
            return {
                "success": True,
                "message": f"Holiday on {holiday_date.strftime('%B %d, %Y')} has been removed. {shop_name} will be open on this day.",
                "deleted_holiday": {
                    "date": holiday_date.isoformat(),
                    "name": holiday_name,
                    "shop": shop_name
                }
            }
            
        except Holiday.DoesNotExist:
            return {"success": False, "error": "Holiday not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"delete_holiday error: {e}")
            return {"success": False, "error": str(e)}


class CreateStaffTool(BaseTool):
    """Add a new staff member to the shop."""
    
    name = "create_staff"
    description = """
    Add a new staff member to the shop.
    Creates a staff record and optionally sends an invitation email.
    The staff member can then sign up to access their schedule.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name of the staff member"
                },
                "email": {
                    "type": "string",
                    "description": "Email address for the staff member"
                },
                "phone": {
                    "type": "string",
                    "description": "Optional: Phone number"
                },
                "bio": {
                    "type": "string",
                    "description": "Optional: Short bio about the staff member"
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop. If not provided, uses first active shop."
                },
                "service_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: List of service names this staff member can provide"
                }
            },
            "required": ["name", "email"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.staff.models import StaffMember, StaffService
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            # Get shop
            shop_id = kwargs.get('shop_id')
            if shop_id:
                shop = Shop.objects.get(id=shop_id, client=client)
            else:
                shop = Shop.objects.filter(client=client, is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            name = kwargs.get('name', '').strip()
            email = kwargs.get('email', '').strip().lower()
            
            if not name:
                return {"success": False, "error": "Staff name is required"}
            if not email:
                return {"success": False, "error": "Staff email is required"}
            
            # Check if email already exists for this shop
            if StaffMember.objects.filter(shop=shop, email=email).exists():
                return {"success": False, "error": f"A staff member with email {email} already exists at {shop.name}"}
            
            # Create staff member
            staff = StaffMember.objects.create(
                shop=shop,
                name=name,
                email=email,
                phone=kwargs.get('phone', ''),
                bio=kwargs.get('bio', ''),
                is_active=True
            )
            
            # Assign services if provided
            assigned_services = []
            service_names = kwargs.get('service_names', [])
            if service_names:
                for service_name in service_names:
                    service = Service.objects.filter(
                        shop=shop, 
                        name__icontains=service_name, 
                        is_active=True
                    ).first()
                    if service:
                        StaffService.objects.create(staff_member=staff, service=service)
                        assigned_services.append(service.name)
            
            logger.info(f"Created staff member {name} at {shop.name}")
            
            return {
                "success": True,
                "message": f"Staff member '{name}' has been added to {shop.name}",
                "staff": {
                    "id": str(staff.id),
                    "name": staff.name,
                    "email": staff.email,
                    "phone": staff.phone,
                    "bio": staff.bio,
                    "shop": shop.name,
                    "assigned_services": assigned_services,
                    "invite_status": staff.invite_status
                }
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found or you don't own this shop"}
        except Exception as e:
            logger.error(f"create_staff error: {e}")
            return {"success": False, "error": str(e)}


class UpdateStaffTool(BaseTool):
    """Update a staff member's information."""
    
    name = "update_staff"
    description = """
    Update information for an existing staff member.
    Can update name, phone, bio, or active status.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "staff_id": {
                    "type": "string",
                    "description": "UUID of the staff member"
                },
                "staff_name": {
                    "type": "string",
                    "description": "Alternative: Find staff by name"
                },
                "name": {
                    "type": "string",
                    "description": "New name for the staff member"
                },
                "phone": {
                    "type": "string",
                    "description": "New phone number"
                },
                "bio": {
                    "type": "string",
                    "description": "New bio"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Set active/inactive status"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.staff.models import StaffMember
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            staff_id = kwargs.get('staff_id')
            staff_name = kwargs.get('staff_name')
            
            if staff_id:
                staff = StaffMember.objects.select_related('shop').get(id=staff_id)
            elif staff_name:
                staff = StaffMember.objects.select_related('shop').filter(
                    shop__client=client,
                    name__icontains=staff_name
                ).first()
            else:
                return {"success": False, "error": "Please provide staff_id or staff_name"}
            
            if not staff:
                return {"success": False, "error": "Staff member not found"}
            
            if staff.shop.client != client:
                return {"success": False, "error": "This staff member is not at your shop"}
            
            # Update fields
            updated_fields = []
            if 'name' in kwargs and kwargs['name']:
                staff.name = kwargs['name']
                updated_fields.append('name')
            if 'phone' in kwargs:
                staff.phone = kwargs['phone']
                updated_fields.append('phone')
            if 'bio' in kwargs:
                staff.bio = kwargs['bio']
                updated_fields.append('bio')
            if 'is_active' in kwargs:
                staff.is_active = kwargs['is_active']
                updated_fields.append('is_active')
            
            if not updated_fields:
                return {"success": False, "error": "No fields to update"}
            
            staff.save()
            logger.info(f"Updated staff member {staff.name}: {updated_fields}")
            
            return {
                "success": True,
                "message": f"Staff member '{staff.name}' has been updated",
                "updated_fields": updated_fields,
                "staff": {
                    "id": str(staff.id),
                    "name": staff.name,
                    "email": staff.email,
                    "phone": staff.phone,
                    "bio": staff.bio,
                    "is_active": staff.is_active,
                    "shop": staff.shop.name
                }
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff member not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"update_staff error: {e}")
            return {"success": False, "error": str(e)}


class CreateServiceTool(BaseTool):
    """Add a new service to the shop."""
    
    name = "create_service"
    description = """
    Add a new service to the shop.
    Services are what customers can book (e.g., Haircut, Manicure).
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the service (e.g., 'Haircut', 'Manicure')"
                },
                "price": {
                    "type": "number",
                    "description": "Price of the service"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes (e.g., 30, 60)"
                },
                "description": {
                    "type": "string",
                    "description": "Optional: Description of the service"
                },
                "category": {
                    "type": "string",
                    "description": "Optional: Category (e.g., 'Hair', 'Nails', 'Spa')"
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop. If not provided, uses first active shop."
                }
            },
            "required": ["name", "price", "duration_minutes"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            # Get shop
            shop_id = kwargs.get('shop_id')
            if shop_id:
                shop = Shop.objects.get(id=shop_id, client=client)
            else:
                shop = Shop.objects.filter(client=client, is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            name = kwargs.get('name', '').strip()
            price = kwargs.get('price')
            duration = kwargs.get('duration_minutes')
            
            if not name:
                return {"success": False, "error": "Service name is required"}
            if price is None or price < 0:
                return {"success": False, "error": "Valid price is required"}
            if duration is None or duration < 5:
                return {"success": False, "error": "Duration must be at least 5 minutes"}
            
            # Check if service already exists
            if Service.objects.filter(shop=shop, name__iexact=name).exists():
                return {"success": False, "error": f"A service named '{name}' already exists at {shop.name}"}
            
            # Create service
            service = Service.objects.create(
                shop=shop,
                name=name,
                price=price,
                duration_minutes=duration,
                description=kwargs.get('description', ''),
                category=kwargs.get('category', ''),
                is_active=True
            )
            
            logger.info(f"Created service {name} at {shop.name}")
            
            return {
                "success": True,
                "message": f"Service '{name}' has been added to {shop.name}",
                "service": {
                    "id": str(service.id),
                    "name": service.name,
                    "price": float(service.price),
                    "duration_minutes": service.duration_minutes,
                    "description": service.description,
                    "category": service.category,
                    "shop": shop.name
                }
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found or you don't own this shop"}
        except Exception as e:
            logger.error(f"create_service error: {e}")
            return {"success": False, "error": str(e)}


class UpdateServiceTool(BaseTool):
    """Update an existing service."""
    
    name = "update_service"
    description = """
    Update an existing service's details.
    Can update name, price, duration, description, category, or active status.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service"
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative: Find service by name"
                },
                "name": {
                    "type": "string",
                    "description": "New name for the service"
                },
                "price": {
                    "type": "number",
                    "description": "New price"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "New duration in minutes"
                },
                "description": {
                    "type": "string",
                    "description": "New description"
                },
                "category": {
                    "type": "string",
                    "description": "New category"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "Set active/inactive status"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            service_id = kwargs.get('service_id')
            service_name = kwargs.get('service_name')
            
            if service_id:
                service = Service.objects.select_related('shop').get(id=service_id)
            elif service_name:
                service = Service.objects.select_related('shop').filter(
                    shop__client=client,
                    name__icontains=service_name
                ).first()
            else:
                return {"success": False, "error": "Please provide service_id or service_name"}
            
            if not service:
                return {"success": False, "error": "Service not found"}
            
            if service.shop.client != client:
                return {"success": False, "error": "This service is not at your shop"}
            
            # Update fields
            updated_fields = []
            if 'name' in kwargs and kwargs['name']:
                service.name = kwargs['name']
                updated_fields.append('name')
            if 'price' in kwargs and kwargs['price'] is not None:
                service.price = kwargs['price']
                updated_fields.append('price')
            if 'duration_minutes' in kwargs and kwargs['duration_minutes']:
                service.duration_minutes = kwargs['duration_minutes']
                updated_fields.append('duration_minutes')
            if 'description' in kwargs:
                service.description = kwargs['description']
                updated_fields.append('description')
            if 'category' in kwargs:
                service.category = kwargs['category']
                updated_fields.append('category')
            if 'is_active' in kwargs:
                service.is_active = kwargs['is_active']
                updated_fields.append('is_active')
            
            if not updated_fields:
                return {"success": False, "error": "No fields to update"}
            
            service.save()
            logger.info(f"Updated service {service.name}: {updated_fields}")
            
            return {
                "success": True,
                "message": f"Service '{service.name}' has been updated",
                "updated_fields": updated_fields,
                "service": {
                    "id": str(service.id),
                    "name": service.name,
                    "price": float(service.price),
                    "duration_minutes": service.duration_minutes,
                    "description": service.description,
                    "category": service.category,
                    "is_active": service.is_active,
                    "shop": service.shop.name
                }
            }
            
        except Service.DoesNotExist:
            return {"success": False, "error": "Service not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"update_service error: {e}")
            return {"success": False, "error": str(e)}


class RescheduleBookingTool(BaseTool):
    """Reschedule an existing booking to a new date/time."""
    
    name = "reschedule_booking"
    description = """
    Reschedule an existing booking to a new date and time.
    For shop owners to help customers change their appointment.
    Checks availability before rescheduling.
    """
    allowed_roles = ["client"]
    
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
                    "description": "New date and time (ISO format or natural language like 'tomorrow at 2pm')"
                },
                "new_staff_id": {
                    "type": "string",
                    "description": "Optional: UUID of new staff member"
                },
                "new_staff_name": {
                    "type": "string",
                    "description": "Optional: Name of new staff member"
                }
            },
            "required": ["booking_id", "new_datetime"]
        }
    
    def _parse_datetime(self, dt_str: str) -> datetime:
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
        
        # Parse natural language
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
        from apps.staff.models import StaffMember
        from apps.clients.models import Client
        from apps.schedules.services.availability import AvailabilityService
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            booking = Booking.objects.select_related('shop', 'service', 'customer__user').get(
                id=kwargs['booking_id']
            )
            
            if booking.shop.client != client:
                return {"success": False, "error": "This booking is not at your shop"}
            
            if booking.status in ['cancelled', 'completed']:
                return {"success": False, "error": f"Cannot reschedule a {booking.status} booking"}
            
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
                    "message": f"Available times on {new_dt.strftime('%B %d')}: {', '.join(suggestions)}"
                }
            
            # Handle staff change if requested
            old_datetime = booking.booking_datetime
            old_staff = booking.staff_member
            
            if kwargs.get('new_staff_id'):
                try:
                    new_staff = StaffMember.objects.get(
                        id=kwargs['new_staff_id'], 
                        shop=booking.shop, 
                        is_active=True
                    )
                    booking.staff_member = new_staff
                except StaffMember.DoesNotExist:
                    pass
            elif kwargs.get('new_staff_name'):
                new_staff = StaffMember.objects.filter(
                    name__icontains=kwargs['new_staff_name'],
                    shop=booking.shop,
                    is_active=True
                ).first()
                if new_staff:
                    booking.staff_member = new_staff
            
            # Update booking
            booking.booking_datetime = new_dt
            booking.save()
            
            logger.info(f"Rescheduled booking {booking.id} from {old_datetime} to {new_dt}")
            
            return {
                "success": True,
                "message": f"Booking rescheduled from {old_datetime.strftime('%B %d at %I:%M %p')} to {new_dt.strftime('%B %d at %I:%M %p')}",
                "booking": {
                    "booking_id": str(booking.id),
                    "customer": booking.customer.user.full_name,
                    "service": booking.service.name,
                    "old_datetime": old_datetime.isoformat(),
                    "new_datetime": new_dt.isoformat(),
                    "formatted_new_datetime": new_dt.strftime("%B %d, %Y at %I:%M %p"),
                    "staff": booking.staff_member.name if booking.staff_member else "To be assigned"
                }
            }
            
        except Booking.DoesNotExist:
            return {"success": False, "error": "Booking not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"reschedule_booking error: {e}")
            return {"success": False, "error": str(e)}


class AssignStaffToServiceTool(BaseTool):
    """Assign a staff member to provide a service."""
    
    name = "assign_staff_to_service"
    description = """
    Assign a staff member to be able to provide a specific service.
    This allows the staff member to be booked for this service.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "staff_id": {
                    "type": "string",
                    "description": "UUID of the staff member"
                },
                "staff_name": {
                    "type": "string",
                    "description": "Alternative: Staff member name"
                },
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service"
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative: Service name"
                },
                "is_primary": {
                    "type": "boolean",
                    "description": "Optional: Set as primary provider for this service. Default: false"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.staff.models import StaffMember, StaffService
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            # Get staff member
            staff_id = kwargs.get('staff_id')
            staff_name = kwargs.get('staff_name')
            
            if staff_id:
                staff = StaffMember.objects.select_related('shop').get(id=staff_id)
            elif staff_name:
                staff = StaffMember.objects.select_related('shop').filter(
                    shop__client=client,
                    name__icontains=staff_name
                ).first()
            else:
                return {"success": False, "error": "Please provide staff_id or staff_name"}
            
            if not staff:
                return {"success": False, "error": "Staff member not found"}
            
            if staff.shop.client != client:
                return {"success": False, "error": "This staff member is not at your shop"}
            
            # Get service
            service_id = kwargs.get('service_id')
            service_name = kwargs.get('service_name')
            
            if service_id:
                service = Service.objects.get(id=service_id, shop=staff.shop)
            elif service_name:
                service = Service.objects.filter(
                    shop=staff.shop,
                    name__icontains=service_name
                ).first()
            else:
                return {"success": False, "error": "Please provide service_id or service_name"}
            
            if not service:
                return {"success": False, "error": "Service not found at this shop"}
            
            # Check if already assigned
            existing = StaffService.objects.filter(staff_member=staff, service=service).first()
            if existing:
                return {"success": False, "error": f"{staff.name} is already assigned to {service.name}"}
            
            # Create assignment
            is_primary = kwargs.get('is_primary', False)
            StaffService.objects.create(
                staff_member=staff,
                service=service,
                is_primary=is_primary
            )
            
            logger.info(f"Assigned {staff.name} to service {service.name}")
            
            return {
                "success": True,
                "message": f"{staff.name} can now provide {service.name}",
                "assignment": {
                    "staff": staff.name,
                    "service": service.name,
                    "is_primary": is_primary,
                    "shop": staff.shop.name
                }
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff member not found"}
        except Service.DoesNotExist:
            return {"success": False, "error": "Service not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"assign_staff_to_service error: {e}")
            return {"success": False, "error": str(e)}


class UpdateShopHoursTool(BaseTool):
    """Update shop operating hours."""
    
    name = "update_shop_hours"
    description = """
    Update the operating hours for a shop on specific days.
    Can change opening/closing time for any day of the week.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "Day of week: monday, tuesday, wednesday, thursday, friday, saturday, sunday",
                    "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                },
                "start_time": {
                    "type": "string",
                    "description": "Opening time (e.g., '9:00 AM', '10:00', '0900')"
                },
                "end_time": {
                    "type": "string",
                    "description": "Closing time (e.g., '6:00 PM', '18:00', '1800')"
                },
                "is_closed": {
                    "type": "boolean",
                    "description": "Set to true to mark the shop as closed on this day"
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop"
                }
            },
            "required": ["day"]
        }
    
    def _parse_time(self, time_str: str):
        """Parse time from various formats."""
        import re
        from datetime import time as dt_time
        
        time_str = time_str.strip().upper()
        
        # Try HH:MM AM/PM format
        match = re.match(r'(\d{1,2}):?(\d{2})?\s*(AM|PM)?', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3)
            
            if ampm == 'PM' and hour < 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0
            
            return dt_time(hour, minute)
        
        raise ValueError(f"Cannot parse time: {time_str}")
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import ShopSchedule
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            shop_id = kwargs.get('shop_id')
            if shop_id:
                shop = Shop.objects.get(id=shop_id, client=client)
            else:
                shop = Shop.objects.filter(client=client, is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            day = kwargs.get('day', '').lower()
            is_closed = kwargs.get('is_closed', False)
            
            # Get or create schedule for this day
            schedule, created = ShopSchedule.objects.get_or_create(
                shop=shop,
                day_of_week=day,
                defaults={
                    'start_time': '09:00',
                    'end_time': '18:00',
                    'is_active': True
                }
            )
            
            if is_closed:
                schedule.is_active = False
                schedule.save()
                return {
                    "success": True,
                    "message": f"{shop.name} is now closed on {day.capitalize()}",
                    "schedule": {
                        "day": day,
                        "status": "closed"
                    }
                }
            
            # Update times
            if kwargs.get('start_time'):
                schedule.start_time = self._parse_time(kwargs['start_time'])
            if kwargs.get('end_time'):
                schedule.end_time = self._parse_time(kwargs['end_time'])
            schedule.is_active = True
            schedule.save()
            
            return {
                "success": True,
                "message": f"Shop hours updated for {day.capitalize()}: {schedule.start_time.strftime('%I:%M %p')} - {schedule.end_time.strftime('%I:%M %p')}",
                "schedule": {
                    "shop": shop.name,
                    "day": day,
                    "start_time": schedule.start_time.strftime('%I:%M %p'),
                    "end_time": schedule.end_time.strftime('%I:%M %p'),
                    "is_open": True
                }
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"update_shop_hours error: {e}")
            return {"success": False, "error": str(e)}


class DeleteServiceTool(BaseTool):
    """Delete (deactivate) a service from the shop."""
    
    name = "delete_service"
    description = """
    Remove a service from the shop's menu.
    The service will be deactivated and no longer available for booking.
    Existing bookings for this service are not affected.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service to delete"
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative: Name of the service to delete"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            service_id = kwargs.get('service_id')
            service_name = kwargs.get('service_name')
            
            if service_id:
                service = Service.objects.select_related('shop').get(id=service_id)
            elif service_name:
                service = Service.objects.select_related('shop').filter(
                    shop__client=client,
                    name__icontains=service_name,
                    is_active=True
                ).first()
            else:
                return {"success": False, "error": "Please provide service_id or service_name"}
            
            if not service:
                return {"success": False, "error": "Service not found"}
            
            if service.shop.client != client:
                return {"success": False, "error": "This service is not at your shop"}
            
            if not service.is_active:
                return {"success": False, "error": "This service is already deleted"}
            
            # Soft delete
            service_name_str = service.name
            shop_name = service.shop.name
            service.is_active = False
            service.save()
            
            logger.info(f"Deleted service {service_name_str} from {shop_name}")
            
            return {
                "success": True,
                "message": f"Service '{service_name_str}' has been removed from {shop_name}",
                "deleted_service": {
                    "name": service_name_str,
                    "shop": shop_name
                }
            }
            
        except Service.DoesNotExist:
            return {"success": False, "error": "Service not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"delete_service error: {e}")
            return {"success": False, "error": str(e)}


class RemoveStaffFromServiceTool(BaseTool):
    """Remove a staff member from providing a service."""
    
    name = "remove_staff_from_service"
    description = """
    Remove a staff member's ability to provide a specific service.
    The staff member will no longer be bookable for this service.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "staff_id": {
                    "type": "string",
                    "description": "UUID of the staff member"
                },
                "staff_name": {
                    "type": "string",
                    "description": "Alternative: Staff member name"
                },
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service"
                },
                "service_name": {
                    "type": "string",
                    "description": "Alternative: Service name"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.staff.models import StaffMember, StaffService
        from apps.services.models import Service
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            # Get staff
            staff_id = kwargs.get('staff_id')
            staff_name = kwargs.get('staff_name')
            
            if staff_id:
                staff = StaffMember.objects.select_related('shop').get(id=staff_id)
            elif staff_name:
                staff = StaffMember.objects.select_related('shop').filter(
                    shop__client=client,
                    name__icontains=staff_name
                ).first()
            else:
                return {"success": False, "error": "Please provide staff_id or staff_name"}
            
            if not staff:
                return {"success": False, "error": "Staff member not found"}
            
            if staff.shop.client != client:
                return {"success": False, "error": "This staff is not at your shop"}
            
            # Get service
            service_id = kwargs.get('service_id')
            service_name = kwargs.get('service_name')
            
            if service_id:
                service = Service.objects.get(id=service_id, shop=staff.shop)
            elif service_name:
                service = Service.objects.filter(
                    shop=staff.shop,
                    name__icontains=service_name
                ).first()
            else:
                return {"success": False, "error": "Please provide service_id or service_name"}
            
            if not service:
                return {"success": False, "error": "Service not found"}
            
            # Remove assignment
            staff_service = StaffService.objects.filter(
                staff_member=staff,
                service=service
            ).first()
            
            if not staff_service:
                return {"success": False, "error": f"{staff.name} is not assigned to {service.name}"}
            
            staff_service.delete()
            
            logger.info(f"Removed {staff.name} from service {service.name}")
            
            return {
                "success": True,
                "message": f"{staff.name} is no longer assigned to provide {service.name}",
                "removed": {
                    "staff": staff.name,
                    "service": service.name,
                    "shop": staff.shop.name
                }
            }
            
        except StaffMember.DoesNotExist:
            return {"success": False, "error": "Staff member not found"}
        except Service.DoesNotExist:
            return {"success": False, "error": "Service not found"}
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"remove_staff_from_service error: {e}")
            return {"success": False, "error": str(e)}


class GetShopAnalyticsTool(BaseTool):
    """Get shop analytics and statistics."""
    
    name = "get_shop_analytics"
    description = """
    Get analytics and statistics for the shop.
    Shows booking counts, revenue, popular services, and staff performance.
    Great for understanding business performance.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Time period: 'today', 'week', 'month', 'year'. Default: month",
                    "enum": ["today", "week", "month", "year"]
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.bookings.models import Booking
        from apps.services.models import Service
        from apps.staff.models import StaffMember
        from apps.clients.models import Client
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            shop_id = kwargs.get('shop_id')
            if shop_id:
                shop = Shop.objects.get(id=shop_id, client=client)
            else:
                shop = Shop.objects.filter(client=client, is_active=True).first()
            
            if not shop:
                return {"success": False, "error": "No shop found"}
            
            period = kwargs.get('period', 'month')
            today = timezone.now().date()
            
            if period == 'today':
                start_date = today
                period_label = "Today"
            elif period == 'week':
                start_date = today - timedelta(days=7)
                period_label = "This Week"
            elif period == 'year':
                start_date = today - timedelta(days=365)
                period_label = "This Year"
            else:  # month
                start_date = today - timedelta(days=30)
                period_label = "Last 30 Days"
            
            # Get bookings for period
            bookings = Booking.objects.filter(
                shop=shop,
                booking_datetime__date__gte=start_date
            )
            
            total_bookings = bookings.count()
            completed_bookings = bookings.filter(status='completed').count()
            cancelled_bookings = bookings.filter(status='cancelled').count()
            pending_bookings = bookings.filter(status='pending').count()
            confirmed_bookings = bookings.filter(status='confirmed').count()
            
            # Revenue (from completed bookings)
            total_revenue = bookings.filter(status='completed').aggregate(
                total=Sum('total_price')
            )['total'] or 0
            
            # Popular services
            popular_services = bookings.filter(status='completed').values(
                'service__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            # Staff performance
            staff_stats = bookings.filter(
                status='completed',
                staff_member__isnull=False
            ).values(
                'staff_member__name'
            ).annotate(
                count=Count('id'),
                revenue=Sum('total_price')
            ).order_by('-count')[:5]
            
            return {
                "success": True,
                "shop": shop.name,
                "period": period_label,
                "summary": {
                    "total_bookings": total_bookings,
                    "completed": completed_bookings,
                    "confirmed": confirmed_bookings,
                    "pending": pending_bookings,
                    "cancelled": cancelled_bookings,
                    "total_revenue": float(total_revenue),
                    "average_revenue_per_booking": float(total_revenue / completed_bookings) if completed_bookings > 0 else 0
                },
                "popular_services": [
                    {"name": s['service__name'], "bookings": s['count']}
                    for s in popular_services
                ],
                "staff_performance": [
                    {
                        "name": s['staff_member__name'],
                        "bookings": s['count'],
                        "revenue": float(s['revenue'] or 0)
                    }
                    for s in staff_stats
                ],
                "message": f"{period_label}: {completed_bookings} completed bookings, ${total_revenue:.2f} revenue"
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            logger.error(f"get_shop_analytics error: {e}")
            return {"success": False, "error": str(e)}

