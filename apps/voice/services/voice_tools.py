"""
Voice-specific tools for querying shops and services.
These are simplified versions optimized for voice responses.
"""
import logging
from typing import Any, Dict, List, Optional
from django.db.models import Q

logger = logging.getLogger(__name__)


# Tool definitions for OpenAI Realtime API
VOICE_TOOLS = [
    {
        "type": "function",
        "name": "search_shops",
        "description": "Search for salons/shops by name, city, or service type. Use this when the user asks to find salons or beauty shops.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - shop name, service type (e.g., 'haircut', 'nails'), or city name"
                },
                "city": {
                    "type": "string",
                    "description": "Optional: Filter by city name"
                }
            }
        }
    },
    {
        "type": "function",
        "name": "get_shop_details",
        "description": "Get detailed information about a specific shop including address, phone, hours, and rating. Use when user asks about a specific shop.",
        "parameters": {
            "type": "object",
            "properties": {
                "shop_name": {
                    "type": "string",
                    "description": "Name of the shop to get details for"
                }
            },
            "required": ["shop_name"]
        }
    },
    {
        "type": "function",
        "name": "get_shop_services",
        "description": "Get services offered by a shop with prices and durations. Use when user asks about services, prices, or what a shop offers.",
        "parameters": {
            "type": "object",
            "properties": {
                "shop_name": {
                    "type": "string",
                    "description": "Name of the shop to get services for"
                }
            },
            "required": ["shop_name"]
        }
    }
]


def search_shops(query: str = "", city: str = "") -> Dict[str, Any]:
    """
    Search for shops by name, city, or service type.
    
    Args:
        query: Search query (shop name, service type, or city)
        city: Optional city filter
        
    Returns:
        Dictionary with search results
    """
    from apps.shops.models import Shop
    
    try:
        shops = Shop.objects.filter(is_active=True)
        
        if query:
            shops = shops.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(city__icontains=query) |
                Q(services__name__icontains=query) |
                Q(services__category__icontains=query)
            ).distinct()
        
        if city:
            shops = shops.filter(city__icontains=city)
        
        shops = shops.order_by('-average_rating')[:10]
        
        if not shops.exists():
            return {
                "success": True,
                "count": 0,
                "message": "No salons found matching your search.",
                "shops": []
            }
        
        shop_list = []
        for shop in shops:
            shop_list.append({
                "name": shop.name,
                "city": shop.city,
                "address": shop.address,
                "rating": float(shop.average_rating),
                "reviews": shop.total_reviews
            })
        
        logger.info(f"Voice search_shops found {len(shop_list)} shops for query='{query}'")
        
        return {
            "success": True,
            "count": len(shop_list),
            "shops": shop_list
        }
        
    except Exception as e:
        logger.error(f"Voice search_shops error: {e}")
        return {"success": False, "error": str(e)}


def get_shop_details(shop_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific shop.
    
    Args:
        shop_name: Name of the shop
        
    Returns:
        Dictionary with shop details
    """
    from apps.shops.models import Shop
    from apps.schedules.models import ShopSchedule
    
    try:
        shop = Shop.objects.filter(
            name__icontains=shop_name,
            is_active=True
        ).first()
        
        if not shop:
            return {
                "success": False,
                "error": f"Could not find a salon named '{shop_name}'"
            }
        
        # Get schedule/hours
        schedules = ShopSchedule.objects.filter(shop=shop, is_active=True)
        
        hours_list = []
        
        for schedule in schedules:
            # day_of_week is stored as a string like 'monday', 'tuesday', etc.
            day_name = schedule.day_of_week.capitalize() if schedule.day_of_week else "Unknown"
            hours_list.append({
                "day": day_name,
                "open": schedule.start_time.strftime("%I:%M %p"),
                "close": schedule.end_time.strftime("%I:%M %p")
            })
        
        logger.info(f"Voice get_shop_details found shop: {shop.name}")
        
        return {
            "success": True,
            "shop": {
                "name": shop.name,
                "address": f"{shop.address}, {shop.city}",
                "phone": shop.phone,
                "email": shop.email or "Not provided",
                "rating": float(shop.average_rating),
                "reviews": shop.total_reviews,
                "hours": hours_list if hours_list else "Hours not set"
            }
        }
        
    except Exception as e:
        logger.error(f"Voice get_shop_details error: {e}")
        return {"success": False, "error": str(e)}


def get_shop_services(shop_name: str) -> Dict[str, Any]:
    """
    Get services offered by a shop.
    
    Args:
        shop_name: Name of the shop
        
    Returns:
        Dictionary with services list
    """
    from apps.shops.models import Shop
    from apps.services.models import Service
    
    try:
        shop = Shop.objects.filter(
            name__icontains=shop_name,
            is_active=True
        ).first()
        
        if not shop:
            return {
                "success": False,
                "error": f"Could not find a salon named '{shop_name}'"
            }
        
        services = Service.objects.filter(
            shop=shop,
            is_active=True
        ).order_by('category', 'price')
        
        if not services.exists():
            return {
                "success": True,
                "shop_name": shop.name,
                "count": 0,
                "message": "This salon has no services listed yet.",
                "services": []
            }
        
        service_list = []
        for service in services:
            service_list.append({
                "name": service.name,
                "category": service.category or "General",
                "price": float(service.price),
                "duration_minutes": service.duration_minutes,
                "description": service.description or ""
            })
        
        logger.info(f"Voice get_shop_services found {len(service_list)} services for {shop.name}")
        
        return {
            "success": True,
            "shop_name": shop.name,
            "count": len(service_list),
            "services": service_list
        }
        
    except Exception as e:
        logger.error(f"Voice get_shop_services error: {e}")
        return {"success": False, "error": str(e)}


def execute_voice_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a voice tool by name.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments
        
    Returns:
        Tool execution result
    """
    tools = {
        "search_shops": search_shops,
        "get_shop_details": get_shop_details,
        "get_shop_services": get_shop_services,
    }
    
    if tool_name not in tools:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    try:
        return tools[tool_name](**arguments)
    except Exception as e:
        logger.error(f"Voice tool execution error for {tool_name}: {e}")
        return {"success": False, "error": str(e)}
