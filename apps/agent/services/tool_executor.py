"""
Tool executor for the AI agent.
Manages and executes all available tools.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from apps.agent.tools.base import BaseTool
from apps.agent.tools.booking_tools import (
    GetMyBookingsTool,
    CreateBookingTool,
    RescheduleMyBookingTool,
    CancelBookingTool,
    GetShopBookingsTool,
    ConfirmBookingTool
)
from apps.agent.tools.shop_tools import (
    SearchShopsTool,
    GetShopInfoTool,
    GetShopServicesTool,
    GetShopStaffTool,
    GetMyShopsTool,
    GetMyStaffTool
)
from apps.agent.tools.schedule_tools import (
    GetAvailableSlotsTool,
    GetShopHoursTool,
    GetShopHolidaysTool
)
from apps.agent.tools.management_tools import (
    CreateHolidayTool,
    DeleteHolidayTool,
    CreateStaffTool,
    UpdateStaffTool,
    CreateServiceTool,
    UpdateServiceTool,
    DeleteServiceTool,
    RescheduleBookingTool,
    AssignStaffToServiceTool,
    RemoveStaffFromServiceTool,
    UpdateShopHoursTool,
    GetShopAnalyticsTool
)
from apps.agent.tools.staff_tools import (
    CompleteBookingTool,
    GetMyScheduleTool,
    GetCustomerHistoryTool,
    GetMyServicesTool,
    GetTodaySummaryTool
)
from apps.agent.tools.deal_tools import (
    GetShopDealsTool,
    GetDealSlotsTool,
    CreateDealBookingTool
)

logger = logging.getLogger(__name__)


# All available tools
ALL_TOOLS: List[BaseTool] = [
    # Booking tools
    GetMyBookingsTool(),
    CreateBookingTool(),
    RescheduleMyBookingTool(),
    CancelBookingTool(),
    GetShopBookingsTool(),
    ConfirmBookingTool(),
    # Shop tools
    SearchShopsTool(),
    GetShopInfoTool(),
    GetShopServicesTool(),
    GetShopStaffTool(),
    GetMyShopsTool(),
    GetMyStaffTool(),
    # Schedule tools
    GetAvailableSlotsTool(),
    GetShopHoursTool(),
    GetShopHolidaysTool(),
    # Management tools (client only)
    CreateHolidayTool(),
    DeleteHolidayTool(),
    CreateStaffTool(),
    UpdateStaffTool(),
    CreateServiceTool(),
    UpdateServiceTool(),
    DeleteServiceTool(),
    RescheduleBookingTool(),
    AssignStaffToServiceTool(),
    RemoveStaffFromServiceTool(),
    UpdateShopHoursTool(),
    GetShopAnalyticsTool(),
    # Staff tools
    CompleteBookingTool(),
    GetMyScheduleTool(),
    GetCustomerHistoryTool(),
    GetMyServicesTool(),
    GetTodaySummaryTool(),
    # Deal tools
    GetShopDealsTool(),
    GetDealSlotsTool(),
    CreateDealBookingTool(),
]


class ToolExecutor:
    """
    Manages tool registration and execution.
    Filters tools based on user role.
    """
    
    def __init__(self, user, role: str):
        """
        Initialize tool executor.
        
        Args:
            user: Authenticated user
            role: User's role (customer, client, staff)
        """
        self.user = user
        self.role = role
        self._tools_map: Dict[str, BaseTool] = {}
        
        # Register tools available for this role
        for tool in ALL_TOOLS:
            if tool.can_use(role):
                self._tools_map[tool.name] = tool
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools available for the current role in OpenAI format.
        
        Returns:
            List of tool definitions for OpenAI
        """
        return [tool.to_openai_function() for tool in self._tools_map.values()]
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None
        """
        return self._tools_map.get(name)
    
    def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            **kwargs: Tool parameters
            
        Returns:
            Tool execution result
        """
        start_time = time.time()
        
        tool = self.get_tool(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' not found or not available for your role"
            }
        
        try:
            logger.info(f"Executing tool: {name} with params: {kwargs}")
            result = tool.execute(self.user, self.role, **kwargs)
            
            execution_time = int((time.time() - start_time) * 1000)
            logger.info(f"Tool {name} completed in {execution_time}ms")
            
            # Add execution metadata
            result['_execution_time_ms'] = execution_time
            result['_tool_name'] = name
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return {
                "success": False,
                "error": f"Error executing tool: {str(e)}",
                "_tool_name": name
            }
    
    def list_tool_names(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools_map.keys())
