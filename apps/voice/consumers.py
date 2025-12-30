"""
WebSocket consumer for voice agent.
Bridges browser audio with OpenAI Realtime API.
Supports Master Agent (platform-wide) and Shop Agents (shop-specific with role-based tools).
"""
import asyncio
import base64
import json
import logging
import time
import uuid
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .services.openai_realtime import OpenAIRealtimeClient
from .voice_agents import MasterVoiceAgent, ShopVoiceAgent

logger = logging.getLogger(__name__)


class VoiceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for voice conversations.
    
    Connection URLs:
    - /ws/voice/ - Master agent (home/browse pages)
    - /ws/voice/shop/{shop_id}/ - Shop agent (shop pages)
    - /ws/voice/?agent=shop&shop_id={uuid} - Alternative shop agent connection
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 pcm16 audio>"}
    - Client sends: {"type": "text", "text": "hello"} (for testing)
    - Client sends: {"type": "end"} to end the session
    
    - Server sends: {"type": "audio", "data": "<base64 pcm16 audio>"}
    - Server sends: {"type": "transcript", "role": "user|assistant", "text": "..."}
    - Server sends: {"type": "status", "status": "connected|disconnected|error"}
    - Server sends: {"type": "agent_switch", "agent_type": "shop", "shop_name": "..."}
    - Server sends: {"type": "error", "message": "..."}
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = str(uuid.uuid4())
        self.openai_client: OpenAIRealtimeClient = None
        self.voice_session = None
        
        # Agent tracking
        self.agent = None  # MasterVoiceAgent or ShopVoiceAgent
        self.agent_type = 'master'
        self.shop = None
        self.user = None
        self.user_role = 'guest'
        
        # Timing for logging
        self._response_start_time = None
    
    async def connect(self):
        """Handle WebSocket connection from browser."""
        await self.accept()
        
        logger.info(f"Voice WebSocket connected: {self.session_id}")
        
        # Get user from scope
        self.user = self.scope.get("user")
        if self.user and not self.user.is_authenticated:
            self.user = None
        
        # Parse query params for agent type and shop
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        requested_agent = query_params.get('agent', ['master'])[0]
        shop_id = query_params.get('shop_id', [None])[0]
        
        # Check URL path for shop ID (from routing)
        url_route = self.scope.get('url_route', {})
        if 'shop_id' in url_route.get('kwargs', {}):
            shop_id = url_route['kwargs']['shop_id']
            requested_agent = 'shop'
        
        # Send connecting status
        await self.send_json({
            "type": "status",
            "status": "connecting",
            "session_id": self.session_id
        })
        
        # Initialize appropriate agent
        if requested_agent == 'shop' and shop_id:
            success = await self._initialize_shop_agent(shop_id)
            if not success:
                # Fall back to master agent
                await self._initialize_master_agent()
        else:
            await self._initialize_master_agent()
        
        # Create session record
        await self._create_session_record()
        
        # Initialize OpenAI Realtime client with agent context
        await self._connect_openai()
    
    async def _initialize_master_agent(self):
        """Initialize the master voice agent."""
        self.agent = MasterVoiceAgent(self.session_id, self.user)
        self.agent_type = 'master'
        self.shop = None
        self.user_role = 'customer' if self.user else 'guest'
        
        logger.info(f"Initialized Master Agent for session {self.session_id}")
    
    async def _initialize_shop_agent(self, shop_id: str) -> bool:
        """Initialize a shop-specific voice agent."""
        shop = await self._get_shop(shop_id)
        
        if not shop:
            logger.warning(f"Shop not found: {shop_id}")
            await self.send_json({
                "type": "error",
                "message": f"Shop not found"
            })
            return False
        
        # Check if shop has active voice agent
        has_agent = await self._check_shop_voice_agent(shop)
        if not has_agent:
            logger.warning(f"Shop {shop.name} doesn't have active voice agent")
        
        self.shop = shop
        self.agent = ShopVoiceAgent(self.session_id, shop, self.user)
        self.agent_type = 'shop'
        self.user_role = self.agent.user_role
        
        logger.info(f"Initialized Shop Agent for {shop.name}, user role: {self.user_role}")
        return True
    
    async def _connect_openai(self):
        """Connect to OpenAI Realtime API with agent configuration."""
        # Get voice from shop agent config if available
        voice = 'alloy'
        if hasattr(self.agent, 'get_voice'):
            voice = self.agent.get_voice()
        
        self.openai_client = OpenAIRealtimeClient(
            on_audio_delta=self._on_audio_delta,
            on_transcript=self._on_transcript,
            on_error=self._on_error,
            on_session_created=self._on_session_created,
            on_tool_call=self._on_tool_call
        )
        
        # Set agent-specific configuration
        system_prompt = self.agent.get_system_prompt()
        tools = self.agent.get_tools()
        
        success = await self.openai_client.connect(
            system_prompt=system_prompt,
            tools=tools,
            voice=voice
        )
        
        if success:
            message = f"Connected to {self.shop.name}" if self.shop else "Voice agent ready"
            await self.send_json({
                "type": "status",
                "status": "connected",
                "agent_type": self.agent_type,
                "shop_name": self.shop.name if self.shop else None,
                "user_role": self.user_role,
                "message": message
            })
            
            # Send custom greeting if available
            if hasattr(self.agent, 'get_greeting'):
                greeting = self.agent.get_greeting()
                if greeting:
                    # Queue greeting as first response
                    await self.openai_client.send_text(f"[GREETING] {greeting}")
        else:
            await self.send_json({
                "type": "error",
                "message": "Failed to connect to voice service"
            })
            await self.close()
    
    async def route_to_shop(self, shop_id: str, shop_name: str = None):
        """
        Route from master agent to shop agent mid-session.
        Called when route_to_shop tool is executed.
        """
        logger.info(f"Routing session {self.session_id} to shop {shop_id}")
        
        # Notify client of agent switch
        await self.send_json({
            "type": "agent_switch",
            "from_agent": "master",
            "to_agent": "shop",
            "shop_id": shop_id,
            "shop_name": shop_name,
            "message": f"Connecting you to {shop_name}..."
        })
        
        # Disconnect current OpenAI session
        if self.openai_client:
            await self.openai_client.disconnect()
        
        # Initialize shop agent
        success = await self._initialize_shop_agent(shop_id)
        
        if success:
            # Update session record
            await self._update_session_agent_type()
            
            # Log the switch
            await self._log_call(
                interaction_type='agent_switch',
                agent_response=f"Switched to shop agent for {self.shop.name}"
            )
            
            # Reconnect to OpenAI with shop agent config
            await self._connect_openai()
        else:
            # Revert to master agent
            await self._initialize_master_agent()
            await self._connect_openai()
            await self.send_json({
                "type": "error",
                "message": "Could not connect to shop. Staying with main agent."
            })
    async def route_to_master(self):
        """
        Route from shop agent back to master agent.
        """
        logger.info(f"Routing session {self.session_id} back to master agent")
        
        # Notify client of agent switch
        await self.send_json({
            "type": "agent_switch",
            "from_agent": "shop",
            "to_agent": "master",
            "message": "Connecting you back to the main assistant..."
        })
        
        # Disconnect current OpenAI session
        if self.openai_client:
            await self.openai_client.disconnect()
        
        # Initialize master agent
        await self._initialize_master_agent()
        
        # Update session record
        await self._update_session_agent_type()
        
        # Log the switch
        await self._log_call(
            interaction_type='agent_switch',
            agent_response="Switched back to master agent"
        )
        
        # Reconnect to OpenAI with master agent config
        await self._connect_openai()
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(f"Voice WebSocket disconnected: {self.session_id}, code: {close_code}")
        
        # Disconnect from OpenAI
        if self.openai_client:
            await self.openai_client.disconnect()
        
        # Update session record
        await self._end_session_record()
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages from browser."""
        try:
            if bytes_data:
                # Binary audio data - forward to OpenAI
                await self._handle_audio(bytes_data)
            elif text_data:
                data = json.loads(text_data)
                msg_type = data.get("type", "")
                
                if msg_type == "audio":
                    # Base64 encoded audio
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await self._handle_audio(audio_bytes)
                
                elif msg_type == "text":
                    # Text input (for testing)
                    text = data.get("text", "")
                    if text and self.openai_client:
                        # Add to agent's conversation history
                        if self.agent:
                            self.agent.add_to_history("user", text)
                        await self.openai_client.send_text(text)
                
                elif msg_type == "end":
                    # End session
                    await self.close()
                
                elif msg_type == "cancel":
                    # Cancel current response
                    if self.openai_client:
                        await self.openai_client.cancel_response()
                
                elif msg_type == "commit":
                    # User stopped speaking - commit audio and get response
                    if self.openai_client:
                        await self.openai_client.commit_audio()
                
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_json({
                "type": "error",
                "message": str(e)
            })
    
    async def _handle_audio(self, audio_bytes: bytes):
        """Forward audio to OpenAI."""
        if self.openai_client and self.openai_client.is_connected:
            await self.openai_client.send_audio(audio_bytes)
    
    def _on_audio_delta(self, audio_b64: str):
        """Callback for audio from OpenAI."""
        asyncio.create_task(self.send_json({
            "type": "audio",
            "data": audio_b64
        }))
    
    def _on_transcript(self, role: str, text: str):
        """Callback for transcripts."""
        # Add to agent's conversation history
        if self.agent:
            self.agent.add_to_history(role, text)
        
        asyncio.create_task(self.send_json({
            "type": "transcript",
            "role": role,
            "text": text
        }))
        
        # Log interaction
        if role == 'user':
            asyncio.create_task(self._log_call(
                interaction_type='user_speech',
                user_input=text
            ))
        else:
            asyncio.create_task(self._log_call(
                interaction_type='assistant_speech',
                agent_response=text
            ))
    
    def _on_error(self, error_msg: str):
        """Callback for errors."""
        asyncio.create_task(self.send_json({
            "type": "error",
            "message": error_msg
        }))
        asyncio.create_task(self._log_call(
            interaction_type='error',
            error_message=error_msg
        ))
    
    def _on_session_created(self, openai_session_id: str):
        """Callback when OpenAI session is created."""
        asyncio.create_task(self._update_openai_session_id(openai_session_id))
    
    def _on_tool_call(self, tool_name: str, tool_args: dict, call_id: str):
        """Callback when OpenAI wants to call a tool."""
        asyncio.create_task(self._execute_tool(tool_name, tool_args, call_id))
    
    async def _execute_tool(self, tool_name: str, tool_args: dict, call_id: str):
        """Execute a tool and return result to OpenAI."""
        start_time = time.time()
        
        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
        
        try:
            # Get tool executor from agent
            executor = self.agent.get_tool_executor()
            
            # Execute tool (may be sync, wrap in sync_to_async)
            from asgiref.sync import sync_to_async
            result = await sync_to_async(executor, thread_sensitive=True)(tool_name, tool_args)
            
            is_agent_switch = False
            
            # Check for special route_to_shop action
            if tool_name == 'route_to_shop' and result.get('success') and result.get('action') == 'route_to_shop':
                # Handle routing
                await self.route_to_shop(
                    result['shop_id'],
                    result.get('shop_name', '')
                )
                # Return success to OpenAI
                result['message'] = f"Successfully connected to {result.get('shop_name', 'the shop')}"
                is_agent_switch = True
            
            # Check for special route_to_master action
            elif tool_name == 'route_to_master' and result.get('success') and result.get('action') == 'route_to_master':
                # Handle routing
                await self.route_to_master()
                result['message'] = "Successfully connected to main assistant"
                is_agent_switch = True
            
            # Log tool call
            execution_time = int((time.time() - start_time) * 1000)
            await self._log_call(
                interaction_type='tool_call',
                tool_name=tool_name,
                tool_input=tool_args,
                tool_output=result,
                tool_success=result.get('success', True),
                response_time_ms=execution_time
            )
            
            # Send result back to OpenAI
            # IMPORTANT: If we switched agents, the old session is dead and the new one 
            # doesn't know about this tool call. So we skip sending the result.
            if not is_agent_switch and self.openai_client and self.openai_client.is_connected:
                await self.openai_client.send_tool_result(call_id, result)
            
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            error_result = {"success": False, "error": str(e)}
            
            await self._log_call(
                interaction_type='tool_call',
                tool_name=tool_name,
                tool_input=tool_args,
                tool_output=error_result,
                tool_success=False,
                error_message=str(e)
            )
            
            if self.openai_client and self.openai_client.is_connected:
                await self.openai_client.send_tool_result(call_id, error_result)
    
    async def send_json(self, data: dict):
        """Send JSON message to browser."""
        try:
            await self.send(text_data=json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    # ============ Database Operations ============
    
    @database_sync_to_async
    def _get_shop(self, shop_id: str):
        """Get shop by ID."""
        from apps.shops.models import Shop
        try:
            return Shop.objects.filter(id=shop_id, is_active=True).first()
        except Exception:
            return None
    
    @database_sync_to_async
    def _check_shop_voice_agent(self, shop) -> bool:
        """Check if shop has an active voice agent."""
        try:
            return hasattr(shop, 'voice_agent') and shop.voice_agent and shop.voice_agent.is_active
        except Exception:
            return False
    
    async def _create_session_record(self):
        """Create VoiceSession record in database."""
        from .models import VoiceSession
        
        @database_sync_to_async
        def create_session():
            return VoiceSession.objects.create(
                session_id=self.session_id,
                user=self.user,
                agent_type=self.agent_type,
                shop=self.shop,
                user_role=self.user_role,
                status='active'
            )
        
        try:
            self.voice_session = await create_session()
            logger.info(f"Created VoiceSession: {self.session_id} ({self.agent_type})")
        except Exception as e:
            logger.error(f"Failed to create VoiceSession: {e}")
    
    async def _update_session_agent_type(self):
        """Update session when agent type changes."""
        @database_sync_to_async
        def update_session():
            if self.voice_session:
                self.voice_session.agent_type = self.agent_type
                self.voice_session.shop = self.shop
                self.voice_session.user_role = self.user_role
                self.voice_session.save(update_fields=['agent_type', 'shop', 'user_role'])
        
        try:
            await update_session()
        except Exception as e:
            logger.error(f"Failed to update session agent type: {e}")
    
    async def _end_session_record(self):
        """Update VoiceSession record when session ends."""
        @database_sync_to_async
        def end_session():
            if self.voice_session:
                self.voice_session.status = 'ended'
                self.voice_session.ended_at = timezone.now()
                if self.voice_session.started_at:
                    duration = (timezone.now() - self.voice_session.started_at).seconds
                    self.voice_session.total_duration_seconds = duration
                self.voice_session.save()
                
                # Update shop voice agent stats
                if self.shop:
                    try:
                        if hasattr(self.shop, 'voice_agent') and self.shop.voice_agent:
                            self.shop.voice_agent.total_sessions += 1
                            self.shop.voice_agent.save(update_fields=['total_sessions'])
                    except Exception:
                        pass
        
        try:
            await end_session()
            logger.info(f"Ended VoiceSession: {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to end VoiceSession: {e}")
    
    async def _update_openai_session_id(self, openai_session_id: str):
        """Update OpenAI session ID in database."""
        @database_sync_to_async
        def update_session():
            if self.voice_session:
                self.voice_session.openai_session_id = openai_session_id
                self.voice_session.save(update_fields=['openai_session_id'])
        
        try:
            await update_session()
        except Exception as e:
            logger.error(f"Failed to update OpenAI session ID: {e}")
    
    async def _log_call(
        self,
        interaction_type: str,
        user_input: str = "",
        agent_response: str = "",
        tool_name: str = "",
        tool_input: dict = None,
        tool_output: dict = None,
        tool_success: bool = True,
        response_time_ms: int = 0,
        error_message: str = ""
    ):
        """Log a call interaction to the database."""
        from .models import VoiceCallLog
        
        @database_sync_to_async
        def log_it():
            if self.voice_session:
                VoiceCallLog.objects.create(
                    session=self.voice_session,
                    agent_type=self.agent_type,
                    shop=self.shop,
                    user_role=self.user_role,
                    interaction_type=interaction_type,
                    user_input=user_input,
                    agent_response=agent_response,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    tool_success=tool_success,
                    response_time_ms=response_time_ms,
                    error_message=error_message
                )
                # Update interaction count
                self.voice_session.total_interactions += 1
                self.voice_session.save(update_fields=['total_interactions'])
        
        try:
            await log_it()
        except Exception as e:
            logger.error(f"Failed to log call: {e}")
