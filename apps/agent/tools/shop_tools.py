"""
Shop and service-related tools for the AI agent.
"""
from typing import Any, Dict
from django.db.models import Q
from .base import BaseTool


class SearchShopsTool(BaseTool):
    """Search for shops."""
    
    name = "search_shops"
    description = """
    Search for shops by name, city, or service type.
    Use this to help customers discover salons.
    """
    allowed_roles = ["customer"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (shop name, city, or service type)"
                },
                "city": {
                    "type": "string",
                    "description": "Optional: Filter by city"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results. Default: 10"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        
        try:
            shops = Shop.objects.filter(is_active=True)
            
            query = kwargs.get('query', '')
            if query:
                shops = shops.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(city__icontains=query) |
                    Q(services__name__icontains=query) |
                    Q(services__category__icontains=query)
                ).distinct()
            
            city = kwargs.get('city')
            if city:
                shops = shops.filter(city__icontains=city)
            
            limit = min(kwargs.get('limit', 10), 20)
            shops = shops.order_by('-average_rating')[:limit]
            
            return {
                "success": True,
                "count": len(shops),
                "shops": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "city": s.city,
                        "address": s.address,
                        "rating": float(s.average_rating),
                        "total_reviews": s.total_reviews,
                        "is_verified": s.is_verified
                    }
                    for s in shops
                ]
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopInfoTool(BaseTool):
    """Get detailed shop information."""
    
    name = "get_shop_info"
    description = """
    Get detailed information about a specific shop.
    Includes location, contact, hours, and ratings.
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
            
            # Get schedule
            schedules = ShopSchedule.objects.filter(shop=shop, is_active=True)
            hours = {}
            for s in schedules:
                hours[s.day_of_week] = {
                    "open": s.start_time.strftime("%I:%M %p"),
                    "close": s.end_time.strftime("%I:%M %p")
                }
            
            return {
                "success": True,
                "shop": {
                    "id": str(shop.id),
                    "name": shop.name,
                    "description": shop.description,
                    "address": shop.address,
                    "city": shop.city,
                    "state": shop.state,
                    "postal_code": shop.postal_code,
                    "phone": shop.phone,
                    "email": shop.email,
                    "website": shop.website,
                    "rating": float(shop.average_rating),
                    "total_reviews": shop.total_reviews,
                    "is_verified": shop.is_verified,
                    "timezone": shop.timezone,
                    "hours": hours
                }
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopServicesTool(BaseTool):
    """Get services offered by a shop."""
    
    name = "get_shop_services"
    description = """
    Get all services offered by a shop.
    Includes names, descriptions, prices, and durations.
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
                "category": {
                    "type": "string",
                    "description": "Optional: Filter by category"
                }
            },
            "required": ["shop_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Service
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            services = Service.objects.filter(shop=shop, is_active=True)
            
            category = kwargs.get('category')
            if category:
                services = services.filter(category__icontains=category)
            
            services = services.order_by('category', 'name')
            
            return {
                "success": True,
                "shop": shop.name,
                "services": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "description": s.description,
                        "category": s.category,
                        "price": float(s.price),
                        "duration_minutes": s.duration_minutes
                    }
                    for s in services
                ]
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopStaffTool(BaseTool):
    """Get staff members at a shop."""
    
    name = "get_shop_staff"
    description = """
    Get staff members who work at a shop.
    Use to help customers choose a preferred stylist.
    """
    allowed_roles = ["customer", "client"]
    
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
                    "description": "Optional: Filter by staff who provide this service"
                }
            },
            "required": ["shop_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.staff.models import StaffMember
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            staff = StaffMember.objects.filter(shop=shop, is_active=True)
            
            service_id = kwargs.get('service_id')
            if service_id:
                staff = staff.filter(services__id=service_id)
            
            staff = staff.prefetch_related('services')
            
            return {
                "success": True,
                "shop": shop.name,
                "staff": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "bio": s.bio,
                        "services": [srv.name for srv in s.services.filter(is_active=True)]
                    }
                    for s in staff
                ]
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
