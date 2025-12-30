"""
Voice Agent Classes for Master and Shop-specific agents.
Uses OpenAI Realtime API with role-based tool access and Pinecone RAG.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from apps.agent.services.context_builder import ContextBuilder
from apps.agent.services.pinecone_service import PineconeService
from apps.agent.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class BaseVoiceAgent(ABC):
    """
    Abstract base class for all voice agents.
    Provides common functionality for Pinecone RAG, context building, and tool management.
    """
    
    def __init__(self, session_id: str, user=None):
        """
        Initialize base voice agent.
        
        Args:
            session_id: Unique session identifier
            user: Authenticated user (can be None for guests)
        """
        self.session_id = session_id
        self.user = user
        
        # Services for RAG and context
        self.context_builder = ContextBuilder()
        self.pinecone_service = PineconeService()
        self.embedding_service = EmbeddingService()
        
        # Conversation history for context
        self.message_history: List[Dict[str, str]] = []
    
    def get_relevant_knowledge(self, query: str, top_k: int = 3) -> Optional[str]:
        """
        Query Pinecone for relevant shop/service information (RAG).
        
        Args:
            query: User's query text
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string or None
        """
        return self.context_builder.get_relevant_knowledge(query, top_k=top_k)
    
    def get_user_context(self, role: str) -> Dict[str, Any]:
        """
        Get user-specific context based on role.
        
        Args:
            role: User's role (customer, client, staff, guest)
            
        Returns:
            Context dictionary with user info, bookings, etc.
        """
        return self.context_builder.build_context(self.user, role)
    
    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history for context."""
        self.message_history.append({"role": role, "content": content})
        # Keep last 20 messages for context
        if len(self.message_history) > 20:
            self.message_history = self.message_history[-20:]
    
    def get_conversation_context(self) -> str:
        """Get formatted conversation history for context."""
        if not self.message_history:
            return ""
        
        context_parts = []
        for msg in self.message_history[-10:]:  # Last 10 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        
        return "\n".join(context_parts)
    
    @abstractmethod
    def get_agent_type(self) -> str:
        """Return the agent type identifier."""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict]:
        """Return OpenAI function definitions for this agent's tools."""
        pass
    
    @abstractmethod
    def get_tool_executor(self) -> Callable:
        """Return a function to execute tools by name."""
        pass


class MasterVoiceAgent(BaseVoiceAgent):
    """
    Platform-level voice agent for browsing and discovering shops.
    Used on Home page and Browse Salons page.
    Can route calls to shop-specific agents.
    """
    
    # Tools available to Master Agent (discovery/search focused)
    TOOL_NAMES = [
        'search_shops',
        'get_shop_info',
        'get_shop_services',
        'get_shop_staff',
        'get_shop_hours',
        'get_shop_holidays',
        'route_to_shop',  # Special routing tool
    ]
    
    def get_agent_type(self) -> str:
        return 'master'
    
    def get_system_prompt(self) -> str:
        """Get system prompt for master agent."""
        from .prompts import get_master_agent_prompt
        
        # Get user context if authenticated
        user_context = None
        if self.user:
            user_context = self.get_user_context('customer')
        
        # Get conversation history
        conversation = self.get_conversation_context()
        
        return get_master_agent_prompt(self.user, user_context, conversation)
    
    def get_tools(self) -> List[Dict]:
        """Get OpenAI function definitions for master agent tools."""
        from .voice_tool_registry import get_master_agent_tools
        return get_master_agent_tools()
    
    def get_tool_executor(self) -> Callable:
        """Get tool executor function."""
        from .voice_tool_registry import execute_master_tool
        return lambda name, args: execute_master_tool(name, args, self.user)


class ShopVoiceAgent(BaseVoiceAgent):
    """
    Shop-specific voice agent with role-based capabilities.
    Provides different tools based on user role (customer, client/owner, staff).
    """
    
    # Tools by role - comprehensive lists
    CUSTOMER_TOOLS = [
        # Discovery
        'get_shop_info',
        'get_shop_services',
        'get_shop_staff',
        'get_shop_hours',
        'get_shop_holidays',
        'get_available_slots',
        # Booking management
        'create_booking',
        'get_my_bookings',
        'cancel_booking',
        'reschedule_my_booking',
    ]
    
    CLIENT_TOOLS = [
        # Shop info (read)
        'get_shop_info',
        'get_shop_services',
        'get_shop_hours',
        'get_shop_holidays',
        'get_available_slots',
        'get_my_shops',
        'get_my_staff',
        # Booking management
        'get_shop_bookings',
        'confirm_booking',
        'cancel_booking',
        'reschedule_booking',
        # Service management
        'create_service',
        'update_service',
        # Staff management
        'create_staff',
        'update_staff',
        'assign_staff_to_service',
        'remove_staff_from_service',
        # Schedule management
        'create_holiday',
        'delete_holiday',
        'update_shop_hours',
        # Customer insights
        'get_customer_history',
    ]
    
    STAFF_TOOLS = [
        # Shop info (read)
        'get_shop_info',
        'get_shop_services',
        'get_shop_hours',
        # Personal schedule
        'get_my_schedule',
        'get_my_bookings',
        'get_my_services',
        'get_today_summary',
        # Booking actions
        'complete_booking',
        # Customer info
        'get_customer_history',
    ]
    
    def __init__(self, session_id: str, shop, user=None):
        """
        Initialize shop voice agent.
        
        Args:
            session_id: Unique session identifier
            shop: Shop model instance
            user: Authenticated user (can be None)
        """
        super().__init__(session_id, user)
        self.shop = shop
        self.user_role = self._determine_role()
    
    def _determine_role(self) -> str:
        """
        Determine user's role for this shop.
        
        Returns:
            Role string: 'customer', 'client', 'staff', or 'guest'
        """
        if not self.user:
            return 'guest'
        
        # Check if user is the shop owner
        try:
            if hasattr(self.user, 'client_profile'):
                client = self.user.client_profile
                if self.shop.client_id == client.id:
                    logger.info(f"User {self.user.email} is owner of {self.shop.name}")
                    return 'client'
        except Exception as e:
            logger.debug(f"Error checking client role: {e}")
        
        # Check if user is staff at this shop
        try:
            if hasattr(self.user, 'staff_profile'):
                staff = self.user.staff_profile
                if staff.shop_id == self.shop.id:
                    logger.info(f"User {self.user.email} is staff at {self.shop.name}")
                    return 'staff'
        except Exception as e:
            logger.debug(f"Error checking staff role: {e}")
        
        # Default to customer
        return 'customer'
    
    def get_agent_type(self) -> str:
        return 'shop'
    
    def get_system_prompt(self) -> str:
        """Get system prompt for shop agent with role-specific context."""
        from .prompts import get_shop_agent_prompt
        
        # Get user context
        user_context = self.get_user_context(self.user_role)
        
        # Get conversation history
        conversation = self.get_conversation_context()
        
        # Get shop-specific agent config
        custom_instructions = ""
        try:
            if hasattr(self.shop, 'voice_agent') and self.shop.voice_agent:
                if self.shop.voice_agent.custom_instructions:
                    custom_instructions = self.shop.voice_agent.custom_instructions
        except Exception:
            pass
        
        return get_shop_agent_prompt(
            shop=self.shop,
            role=self.user_role,
            user=self.user,
            user_context=user_context,
            conversation=conversation,
            custom_instructions=custom_instructions
        )
    
    def get_tools(self) -> List[Dict]:
        """Get OpenAI function definitions based on user role."""
        from .voice_tool_registry import get_shop_agent_tools
        return get_shop_agent_tools(self.user_role)
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names available for user's role."""
        if self.user_role == 'client':
            return self.CLIENT_TOOLS
        elif self.user_role == 'staff':
            return self.STAFF_TOOLS
        else:  # customer or guest
            return self.CUSTOMER_TOOLS
    
    def get_tool_executor(self) -> Callable:
        """Get tool executor function with shop context."""
        from .voice_tool_registry import execute_shop_tool
        return lambda name, args: execute_shop_tool(
            name, args, self.user, self.user_role, self.shop
        )
    
    def get_voice(self) -> str:
        """Get the configured voice for this shop's agent."""
        try:
            if hasattr(self.shop, 'voice_agent') and self.shop.voice_agent:
                return self.shop.voice_agent.voice
        except Exception:
            pass
        return 'alloy'  # Default voice
    
    def get_greeting(self) -> Optional[str]:
        """Get greeting for this shop agent."""
        try:
            # Check for custom greeting first
            if hasattr(self.shop, 'voice_agent') and self.shop.voice_agent:
                if self.shop.voice_agent.custom_greeting:
                    return self.shop.voice_agent.custom_greeting
        except Exception:
            pass
        
        # Return default greeting if no custom greeting
        return f"Welcome to {self.shop.name}! How can I help you today?"
