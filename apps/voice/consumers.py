"""
WebSocket consumer for voice agent.
Bridges browser audio with OpenAI Realtime API.
"""
import asyncio
import base64
import json
import logging
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .services.openai_realtime import OpenAIRealtimeClient

logger = logging.getLogger(__name__)


class VoiceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for voice conversations.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 pcm16 audio>"}
    - Client sends: {"type": "text", "text": "hello"} (for testing)
    - Client sends: {"type": "end"} to end the session
    
    - Server sends: {"type": "audio", "data": "<base64 pcm16 audio>"}
    - Server sends: {"type": "transcript", "role": "user|assistant", "text": "..."}
    - Server sends: {"type": "status", "status": "connected|disconnected|error"}
    - Server sends: {"type": "error", "message": "..."}
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = str(uuid.uuid4())
        self.openai_client: OpenAIRealtimeClient = None
        self.voice_session = None
    
    async def connect(self):
        """Handle WebSocket connection from browser."""
        await self.accept()
        
        logger.info(f"Voice WebSocket connected: {self.session_id}")
        
        # Send connected status
        await self.send_json({
            "type": "status",
            "status": "connecting",
            "session_id": self.session_id
        })
        
        # Initialize OpenAI Realtime client
        self.openai_client = OpenAIRealtimeClient(
            on_audio_delta=self._on_audio_delta,
            on_transcript=self._on_transcript,
            on_error=self._on_error,
            on_session_created=self._on_session_created
        )
        
        # Connect to OpenAI
        success = await self.openai_client.connect()
        
        if success:
            await self.send_json({
                "type": "status",
                "status": "connected",
                "message": "Voice agent ready. Start speaking!"
            })
            
            # Create voice session record
            await self._create_session_record()
        else:
            await self.send_json({
                "type": "error",
                "message": "Failed to connect to voice service"
            })
            await self.close()
    
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
        asyncio.create_task(self.send_json({
            "type": "transcript",
            "role": role,
            "text": text
        }))
        
        # Log interaction
        asyncio.create_task(self._log_interaction(role, text))
    
    def _on_error(self, error_msg: str):
        """Callback for errors."""
        asyncio.create_task(self.send_json({
            "type": "error",
            "message": error_msg
        }))
    
    def _on_session_created(self, openai_session_id: str):
        """Callback when OpenAI session is created."""
        asyncio.create_task(self._update_openai_session_id(openai_session_id))
    
    async def send_json(self, data: dict):
        """Send JSON message to browser."""
        try:
            await self.send(text_data=json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def _create_session_record(self):
        """Create VoiceSession record in database."""
        from .models import VoiceSession
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def create_session():
            user = self.scope.get("user")
            if user and user.is_authenticated:
                return VoiceSession.objects.create(
                    session_id=self.session_id,
                    user=user,
                    status='active'
                )
            else:
                return VoiceSession.objects.create(
                    session_id=self.session_id,
                    status='active'
                )
        
        try:
            self.voice_session = await create_session()
            logger.info(f"Created VoiceSession: {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to create VoiceSession: {e}")
    
    async def _end_session_record(self):
        """Update VoiceSession record when session ends."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def end_session():
            if self.voice_session:
                self.voice_session.status = 'ended'
                self.voice_session.ended_at = timezone.now()
                if self.voice_session.started_at:
                    duration = (timezone.now() - self.voice_session.started_at).seconds
                    self.voice_session.total_duration_seconds = duration
                self.voice_session.save()
        
        try:
            await end_session()
            logger.info(f"Ended VoiceSession: {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to end VoiceSession: {e}")
    
    async def _update_openai_session_id(self, openai_session_id: str):
        """Update OpenAI session ID in database."""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def update_session():
            if self.voice_session:
                self.voice_session.openai_session_id = openai_session_id
                self.voice_session.save(update_fields=['openai_session_id'])
        
        try:
            await update_session()
        except Exception as e:
            logger.error(f"Failed to update OpenAI session ID: {e}")
    
    async def _log_interaction(self, role: str, text: str):
        """Log an interaction to the database."""
        from .models import VoiceInteraction
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def log_it():
            if self.voice_session:
                interaction_type = 'user_speech' if role == 'user' else 'assistant_speech'
                VoiceInteraction.objects.create(
                    session=self.voice_session,
                    interaction_type=interaction_type,
                    content=text
                )
                # Update interaction count
                self.voice_session.total_interactions += 1
                self.voice_session.save(update_fields=['total_interactions'])
        
        try:
            await log_it()
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")
