"""
Voice Tool Registry - Adapts existing agent tools for voice use.
Provides role-based tool access and the RouteToShopTool for master agent.
"""
import logging
from typing import Any, Dict, List

from apps.agent.tools.base import BaseTool

# Import all existing tools
from apps.agent.tools.booking_tools import (
    GetMyBookingsTool,
    CreateBookingTool,
    RescheduleMyBookingTool,
    CancelBookingTool,
    GetShopBookingsTool,
    ConfirmBookingTool,
)
from apps.agent.tools.shop_tools import (
    SearchShopsTool,
    GetMyShopsTool,
    GetShopInfoTool,
    GetShopServicesTool,
    GetMyStaffTool,
    GetShopStaffTool,
)
from apps.agent.tools.schedule_tools import (
    GetAvailableSlotsTool,
    GetShopHoursTool,
    GetShopHolidaysTool,
)
from apps.agent.tools.management_tools import (
    CreateHolidayTool,
    DeleteHolidayTool,
    CreateStaffTool,
    UpdateStaffTool,
    CreateServiceTool,
    UpdateServiceTool,
    RescheduleBookingTool,
    AssignStaffToServiceTool,
)
from apps.agent.tools.staff_tools import (
    CompleteBookingTool,
    GetMyScheduleTool,
    GetCustomerHistoryTool,
    GetMyServicesTool,
    GetTodaySummaryTool,
)
from apps.agent.tools.deal_tools import (
    GetShopDealsTool,
    GetDealSlotsTool,
    CreateDealBookingTool,
)

logger = logging.getLogger(__name__)


# ============ ROUTE TO SHOP TOOL (Master Agent Only) ============

class RouteToShopTool(BaseTool):
    """
    Route the call from master agent to a specific shop's agent.
    This is a special tool that triggers agent switching.
    """
    name = "route_to_shop"
    description = """
    Transfer this call to a specific shop's voice agent.
    Use when the user wants to:
    - Book an appointment at a specific shop
    - Manage bookings at a shop
    - Get personalized help from a shop's assistant
    
    After routing, the shop's agent will handle the conversation with
    role-specific capabilities (booking, management, etc.)
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_name": {
                    "type": "string",
                    "description": "Name of the shop to connect to (partial match supported)"
                },
                "shop_id": {
                    "type": "string",
                    "description": "Optional: UUID of the shop if known"
                }
            },
            "required": ["shop_name"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        """Find the shop and return routing info."""
        from apps.shops.models import Shop
        from django.db.models import Q
        import re
        
        shop_name = kwargs.get('shop_name', '').strip()
        shop_id = kwargs.get('shop_id')
        
        try:
            shop = None
            if shop_id:
                shop = Shop.objects.filter(id=shop_id, is_active=True).first()
            
            if not shop and shop_name:
                # 1. Exact case-insensitive match
                shop = Shop.objects.filter(name__iexact=shop_name, is_active=True).first()
                
                # 2. Match with 'and' / '&' substitution
                if not shop:
                    normalized = shop_name.lower().replace(" and ", " & ")
                    shop = Shop.objects.filter(name__iexact=normalized, is_active=True).first()
                    
                    if not shop:
                        normalized = shop_name.lower().replace(" & ", " and ")
                        shop = Shop.objects.filter(name__iexact=normalized, is_active=True).first()
                
                # 3. Partial match (original)
                if not shop:
                    shop = Shop.objects.filter(name__icontains=shop_name, is_active=True).first()
                
                # 4. Partial split match (e.g. "Andy" in "Andy & Wendi")
                if not shop:
                    # Clean up query (remove 'salon', 'shop', special chars)
                    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', shop_name)
                    parts = clean_name.split()
                    if parts:
                        # Search for first significant part
                        first_part = parts[0]
                        if len(first_part) > 2:
                            # Try to find shops containing the first word
                            candidates = Shop.objects.filter(name__icontains=first_part, is_active=True)
                            
                            if len(parts) > 1:
                                # If multiple words, try to filter candidates that match other words too
                                for candidate in candidates:
                                    # Simple check if other parts match vaguely
                                    score = 0
                                    for part in parts:
                                        if part.lower() in candidate.name.lower():
                                            score += 1
                                    if score >= len(parts) * 0.7:  # 70% match
                                        shop = candidate
                                        break
                            
                            if not shop and candidates.exists():
                                # Just take the first valid candidate if exact match logic failed
                                shop = candidates.first()

            if not shop:
                # Get some suggestions for the error message
                shops = Shop.objects.filter(is_active=True)[:5]
                suggestion_list = [{"id": str(s.id), "name": s.name, "city": s.city} for s in shops]
                
                return {
                    "success": False,
                    "error": f"No shop found match '{shop_name}'",
                    "suggestions": suggestion_list,
                    "message": f"I couldn't find a shop named '{shop_name}'. I can see shops like {', '.join([s['name'] for s in suggestion_list[:3]])}."
                }
            
            # Check if shop has an active voice agent
            has_voice_agent = (
                hasattr(shop, 'voice_agent') and 
                shop.voice_agent and 
                shop.voice_agent.is_active
            )
            
            return {
                "success": True,
                "action": "route_to_shop",
                "shop_id": str(shop.id),
                "shop_name": shop.name,
                "shop_city": shop.city,
                "has_voice_agent": has_voice_agent,
                "message": f"Connecting you to {shop.name}..."
            }
            
        except Exception as e:
            logger.error(f"RouteToShopTool error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# ============ ROUTE TO MASTER TOOL (Shop Agent Only) ============

class RouteToMasterTool(BaseTool):
    """
    Route the call back to the master agent.
    Use when the user wants to switch shops or ends their business at the current shop.
    """
    name = "route_to_master"
    description = """
    Transfer the call back to the main BeautyDrop assistant (Master Agent).
    Use this when:
    - User wants to find a different shop
    - User is done with the current shop but wants to do something else
    - User explicitly asking to "go back" or "talk to main agent"
    - User is unsatisfied with current shop services
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Optional reason for switching back"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        return {
            "success": True,
            "action": "route_to_master",
            "message": "Connecting you back to the main assistant..."
        }


# ============ TOOL INSTANCES ============

# Create singleton instances of all tools
_TOOL_INSTANCES = {
    # Booking tools
    'get_my_bookings': GetMyBookingsTool(),
    'create_booking': CreateBookingTool(),
    'reschedule_my_booking': RescheduleMyBookingTool(),
    'cancel_booking': CancelBookingTool(),
    'get_shop_bookings': GetShopBookingsTool(),
    'confirm_booking': ConfirmBookingTool(),
    
    # Shop tools
    'search_shops': SearchShopsTool(),
    'get_my_shops': GetMyShopsTool(),
    'get_shop_info': GetShopInfoTool(),
    'get_shop_services': GetShopServicesTool(),
    'get_my_staff': GetMyStaffTool(),
    'get_shop_staff': GetShopStaffTool(),
    
    # Schedule tools
    'get_available_slots': GetAvailableSlotsTool(),
    'get_shop_hours': GetShopHoursTool(),
    'get_shop_holidays': GetShopHolidaysTool(),
    
    # Management tools (client/owner)
    'create_holiday': CreateHolidayTool(),
    'delete_holiday': DeleteHolidayTool(),
    'create_staff': CreateStaffTool(),
    'update_staff': UpdateStaffTool(),
    'create_service': CreateServiceTool(),
    'update_service': UpdateServiceTool(),
    'reschedule_booking': RescheduleBookingTool(),
    'assign_staff_to_service': AssignStaffToServiceTool(),
    
    # Staff tools
    'complete_booking': CompleteBookingTool(),
    'get_my_schedule': GetMyScheduleTool(),
    'get_customer_history': GetCustomerHistoryTool(),
    'get_my_services': GetMyServicesTool(),
    'get_today_summary': GetTodaySummaryTool(),
    
    # Voice-specific tools
    'route_to_shop': RouteToShopTool(),
    'route_to_master': RouteToMasterTool(),
    
    # Deal tools
    'get_shop_deals': GetShopDealsTool(),
    'get_deal_slots': GetDealSlotsTool(),
    'create_deal_booking': CreateDealBookingTool(),
}


def to_realtime_tool(tool: BaseTool) -> Dict[str, Any]:
    """
    Convert a tool to OpenAI Realtime API format.
    Realtime API expects 'name', 'description', 'parameters' at the top level
    (unlike Chat Completions which wraps them in 'function').
    """
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters
    }


# ============ MASTER AGENT TOOLS ============

MASTER_AGENT_TOOL_NAMES = [
    'search_shops',
    'get_shop_info',
    'get_shop_services',
    'get_shop_deals',  # Added for deals
    'get_shop_staff',
    'get_shop_hours',
    'get_shop_holidays',
    'route_to_shop',
]


def get_master_agent_tools() -> List[Dict]:
    """Get OpenAI function definitions for master agent."""
    tools = []
    for name in MASTER_AGENT_TOOL_NAMES:
        if name in _TOOL_INSTANCES:
            tools.append(to_realtime_tool(_TOOL_INSTANCES[name]))
    return tools


def execute_master_tool(tool_name: str, args: Dict, user) -> Dict[str, Any]:
    """Execute a master agent tool."""
    if tool_name not in MASTER_AGENT_TOOL_NAMES:
        return {"success": False, "error": f"Tool '{tool_name}' not available for master agent"}
    
    if tool_name not in _TOOL_INSTANCES:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    tool = _TOOL_INSTANCES[tool_name]
    role = 'customer' if user else 'guest'
    
    try:
        return tool.execute(user, role, **args)
    except Exception as e:
        logger.error(f"Master tool execution error for {tool_name}: {e}")
        return {"success": False, "error": str(e)}


# ============ SHOP AGENT TOOLS ============

SHOP_CUSTOMER_TOOLS = [
    'get_shop_info',
    'get_shop_services',
    'get_shop_deals',  # Added for deals
    'get_shop_staff',
    'get_shop_hours',
    'get_shop_holidays',
    'get_available_slots',
    'get_deal_slots',  # Added for deals
    'create_booking',
    'create_deal_booking',  # Added for deals
    'get_my_bookings',
    'cancel_booking',
    'reschedule_my_booking',
    'route_to_master',  # Added
]

SHOP_CLIENT_TOOLS = [
    # Read
    'get_shop_info',
    'get_shop_services',
    'get_shop_deals',  # Added for deals
    'get_shop_hours',
    'get_shop_holidays',
    'get_available_slots',
    'get_deal_slots',  # Added for deals
    'get_my_shops',
    'get_my_staff',
    'get_shop_staff',
    # Bookings
    'get_shop_bookings',
    'confirm_booking',
    'cancel_booking',
    'reschedule_booking',
    # Services
    'create_service',
    'update_service',
    # Staff
    'create_staff',
    'update_staff',
    'assign_staff_to_service',
    # Schedule
    'create_holiday',
    'delete_holiday',
    # Insights
    'get_customer_history',
    'route_to_master',  # Added
]

SHOP_STAFF_TOOLS = [
    'get_shop_info',
    'get_shop_services',
    'get_shop_deals',  # Added for deals
    'get_shop_hours',
    'get_my_schedule',
    'get_my_bookings',
    'get_my_services',
    'get_today_summary',
    'complete_booking',
    'get_customer_history',
    'route_to_master',  # Added
]


def get_shop_agent_tools(role: str) -> List[Dict]:
    """Get OpenAI function definitions for shop agent based on role."""
    if role == 'client':
        tool_names = SHOP_CLIENT_TOOLS
    elif role == 'staff':
        tool_names = SHOP_STAFF_TOOLS
    else:  # customer or guest
        tool_names = SHOP_CUSTOMER_TOOLS
    
    tools = []
    for name in tool_names:
        if name in _TOOL_INSTANCES:
            tools.append(to_realtime_tool(_TOOL_INSTANCES[name]))
    return tools


def execute_shop_tool(
    tool_name: str, 
    args: Dict, 
    user, 
    role: str, 
    shop
) -> Dict[str, Any]:
    """
    Execute a shop agent tool with role and shop context.
    
    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments
        user: Authenticated user
        role: User's role (customer, client, staff)
        shop: Shop model instance
    """
    # Validate tool access based on role
    if role == 'client':
        allowed_tools = SHOP_CLIENT_TOOLS
    elif role == 'staff':
        allowed_tools = SHOP_STAFF_TOOLS
    else:
        allowed_tools = SHOP_CUSTOMER_TOOLS
    
    if tool_name not in allowed_tools:
        return {
            "success": False, 
            "error": f"Tool '{tool_name}' not available for role '{role}'"
        }
    
    if tool_name not in _TOOL_INSTANCES:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    tool = _TOOL_INSTANCES[tool_name]
    
    # Inject shop_id for tools that need it
    shop_tools = [
        'get_shop_info', 'get_shop_services', 'get_shop_deals', 'get_shop_staff',
        'get_shop_hours', 'get_shop_holidays', 'get_available_slots',
        'get_shop_bookings', 'create_holiday', 'delete_holiday',
        'create_service', 'update_service', 'create_staff', 'update_staff',
    ]
    
    if tool_name in shop_tools and 'shop_id' not in args:
        args['shop_id'] = str(shop.id)
    
    # Inject shop_name for search-based tools
    if tool_name == 'create_booking' and 'shop_name' not in args and 'shop_id' not in args:
        args['shop_id'] = str(shop.id)
    
    try:
        result = tool.execute(user, role, **args)
        return result
    except Exception as e:
        logger.error(f"Shop tool execution error for {tool_name}: {e}")
        return {"success": False, "error": str(e)}


# ============ UTILITY FUNCTIONS ============

def get_all_tool_names() -> List[str]:
    """Get all available tool names."""
    return list(_TOOL_INSTANCES.keys())


def get_tool_by_name(name: str) -> BaseTool:
    """Get a tool instance by name."""
    return _TOOL_INSTANCES.get(name)
