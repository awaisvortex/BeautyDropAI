"""
Main AI Agent Controller.
Orchestrates conversation flow, tool calling, and response generation.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

from django.conf import settings

from ..models import ChatSession, ChatMessage, AgentAction
from ..prompts.system_prompts import get_system_prompt
from .context_builder import ContextBuilder
from .tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


class AgentController:
    """
    Main controller for the AI agent.
    Handles conversation flow, OpenAI API calls, and tool execution.
    """
    
    MAX_TOOL_ITERATIONS = 5
    MAX_HISTORY_MESSAGES = 20
    
    def __init__(self, user, session: ChatSession):
        """
        Initialize agent controller.
        
        Args:
            user: Authenticated user
            session: ChatSession instance
        """
        self.user = user
        self.session = session
        self.role = session.user_role
        self._client = None
        
        # Initialize services
        self.context_builder = ContextBuilder()
        self.tool_executor = ToolExecutor(user, self.role)
    
    @property
    def client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client
    
    def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and return the agent's response.
        
        Args:
            user_message: The user's message
            
        Returns:
            Dictionary with response and metadata
        """
        start_time = time.time()
        actions_taken = []
        
        try:
            # Build context
            context = self.context_builder.build_context(
                self.user, self.role, self.session
            )
            
            # Get RAG knowledge if relevant
            knowledge = self.context_builder.get_relevant_knowledge(user_message)
            
            # Build messages
            messages = self._build_messages(user_message, context, knowledge)
            
            # Get available tools
            tools = self.tool_executor.get_available_tools()
            
            # Call OpenAI
            response = self._call_openai(messages, tools)
            
            total_prompt_tokens = response.usage.prompt_tokens
            total_completion_tokens = response.usage.completion_tokens
            request_id = getattr(response, 'id', '')
            model_used = response.model
            
            # Handle tool calls in a loop
            iteration = 0
            while response.choices[0].message.tool_calls and iteration < self.MAX_TOOL_ITERATIONS:
                tool_calls = response.choices[0].message.tool_calls
                
                # Add assistant message with tool calls to conversation
                messages.append(response.choices[0].message.model_dump())
                
                # Execute each tool
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Executing tool: {tool_name}")
                    result = self.tool_executor.execute_tool(tool_name, **tool_args)
                    
                    # Track action
                    actions_taken.append({
                        "action_type": tool_name,
                        "success": result.get('success', False),
                        "details": {k: v for k, v in result.items() if not k.startswith('_')}
                    })
                    
                    # Log action to database
                    self._log_action(tool_name, tool_args, result)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
                
                # Continue conversation
                response = self._call_openai(messages, tools)
                total_prompt_tokens += response.usage.prompt_tokens
                total_completion_tokens += response.usage.completion_tokens
                iteration += 1
            
            # Get final response
            assistant_message = response.choices[0].message.content or ""
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "response": assistant_message,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "request_id": request_id,
                "model": model_used,
                "processing_time_ms": processing_time,
                "actions_taken": actions_taken
            }
            
        except Exception as e:
            logger.error(f"Error in agent controller: {e}")
            processing_time = int((time.time() - start_time) * 1000)
            return {
                "response": "I'm sorry, I encountered an error processing your request. Please try again.",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "request_id": "",
                "model": "",
                "processing_time_ms": processing_time,
                "actions_taken": [],
                "error": str(e)
            }
    
    def _build_messages(
        self, 
        user_message: str, 
        context: Dict[str, Any],
        knowledge: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Build message list for OpenAI API."""
        messages = []
        
        # System prompt
        system_prompt = get_system_prompt(self.role, context)
        messages.append({"role": "system", "content": system_prompt})
        
        # Add RAG knowledge if available
        if knowledge:
            messages.append({
                "role": "system",
                "content": f"Here is relevant information from the knowledge base:\n\n{knowledge}"
            })
        
        # Add context summary
        context_summary = self._format_context_summary(context)
        if context_summary:
            messages.append({
                "role": "system",
                "content": f"Current context:\n{context_summary}"
            })
        
        # Add conversation history
        history = self.session.messages.filter(
            role__in=['user', 'assistant']
        ).order_by('-created_at')[:self.MAX_HISTORY_MESSAGES]
        
        for msg in reversed(list(history)):
            messages.append({"role": msg.role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _format_context_summary(self, context: Dict[str, Any]) -> str:
        """Format context into a readable summary."""
        parts = []
        
        # Add role-specific context
        if self.role == 'customer':
            upcoming = context.get('upcoming_bookings', [])
            if upcoming:
                parts.append(f"Upcoming bookings: {len(upcoming)}")
        
        elif self.role == 'client':
            shop_info = context.get('shop_info', {})
            if shop_info:
                parts.append(f"Shop: {shop_info.get('name', 'Unknown')}")
            
            pending = context.get('pending_bookings_count', 0)
            if pending:
                parts.append(f"Pending confirmations: {pending}")
            
            today = context.get('today_bookings', [])
            if today:
                parts.append(f"Today's bookings: {len(today)}")
        
        elif self.role == 'staff':
            shop_info = context.get('shop_info', {})
            if shop_info:
                parts.append(f"Shop: {shop_info.get('name', 'Unknown')}")
            
            today = context.get('today_bookings', [])
            if today:
                parts.append(f"Today's appointments: {len(today)}")
        
        return "\n".join(parts)
    
    def _call_openai(self, messages: List[Dict], tools: List[Dict]) -> Any:
        """Make API call to OpenAI."""
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-4-turbo-preview')
        
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.7,
            max_tokens=1500
        )
    
    def _log_action(self, tool_name: str, input_params: Dict, result: Dict):
        """Log an agent action to the database."""
        try:
            # Get the last assistant message for this session
            last_message = self.session.messages.filter(role='assistant').order_by('-created_at').first()
            
            if not last_message:
                # Create a placeholder message if none exists
                last_message = ChatMessage.objects.create(
                    session=self.session,
                    role='assistant',
                    content='[Tool execution]',
                    tool_name=tool_name
                )
            
            # Map tool names to action types
            action_type_map = {
                'create_booking': 'booking_create',
                'cancel_booking': 'booking_cancel',
                'confirm_booking': 'booking_confirm',
                'get_my_bookings': 'booking_list',
                'get_shop_bookings': 'booking_list',
                'search_shops': 'shop_search',
                'get_shop_info': 'shop_info',
                'get_shop_services': 'service_list',
                'get_shop_staff': 'staff_list',
                'get_available_slots': 'availability_check',
                'get_shop_hours': 'schedule_info',
                'get_shop_holidays': 'schedule_info',
            }
            
            action_type = action_type_map.get(tool_name, 'shop_info')
            
            # Get related objects from result
            shop_id = input_params.get('shop_id') or result.get('shop_id')
            booking_id = result.get('booking', {}).get('booking_id') or result.get('booking_id')
            
            from apps.shops.models import Shop
            from apps.bookings.models import Booking
            
            shop = None
            booking = None
            
            if shop_id:
                try:
                    shop = Shop.objects.get(id=shop_id)
                except Shop.DoesNotExist:
                    pass
            
            if booking_id:
                try:
                    booking = Booking.objects.get(id=booking_id)
                except Booking.DoesNotExist:
                    pass
            
            AgentAction.objects.create(
                message=last_message,
                action_type=action_type,
                input_params=input_params,
                output_result=result,
                success=result.get('success', False),
                error_message=result.get('error', ''),
                execution_time_ms=result.get('_execution_time_ms', 0),
                shop=shop,
                booking=booking
            )
            
        except Exception as e:
            logger.error(f"Error logging action: {e}")
