"""
OpenAI Realtime API client for voice conversations.
Handles WebSocket connection, audio streaming, and function calling.
"""
import asyncio
import base64
import json
import logging
from typing import Any, Callable, Dict, Optional

import websockets
from django.conf import settings

from .voice_tools import VOICE_TOOLS, execute_voice_tool
from ..prompts import get_voice_system_prompt

logger = logging.getLogger(__name__)

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
OPENAI_REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"


class OpenAIRealtimeClient:
    """
    Client for OpenAI's Realtime API.
    Handles bidirectional audio streaming and function calling.
    """
    
    def __init__(
        self,
        on_audio_delta: Optional[Callable[[bytes], None]] = None,
        on_transcript: Optional[Callable[[str, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_session_created: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the Realtime client.
        
        Args:
            on_audio_delta: Callback for audio data chunks (base64 encoded)
            on_transcript: Callback for transcripts (role, text)
            on_error: Callback for errors
            on_session_created: Callback when session is created
        """
        self.api_key = settings.OPENAI_API_KEY
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        
        # Callbacks
        self.on_audio_delta = on_audio_delta
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.on_session_created = on_session_created
        
        # State
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None
        
        # Transcript accumulator for streaming responses
        self._current_assistant_transcript = ""
    
    async def connect(self) -> bool:
        """
        Connect to OpenAI Realtime API.
        
        Returns:
            True if connection successful
        """
        try:
            url = f"{OPENAI_REALTIME_URL}?model={OPENAI_REALTIME_MODEL}"
            
            headers = [
                ("Authorization", f"Bearer {self.api_key}"),
                ("OpenAI-Beta", "realtime=v1")
            ]
            
            logger.info(f"Connecting to OpenAI Realtime API...")
            
            # websockets 12.0+ uses extra_headers as a list of tuples
            self.ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self._connected = True
            logger.info("Connected to OpenAI Realtime API")
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Configure session
            await self._configure_session()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime: {e}")
            if self.on_error:
                self.on_error(f"Connection failed: {str(e)}")
            return False
    
    async def _configure_session(self):
        """Configure the session with system prompt and tools."""
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": get_voice_system_prompt(),
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "tools": VOICE_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.7
            }
        }
        
        await self._send(config)
        logger.info("Session configured with voice agent settings")
    
    async def _send(self, data: dict):
        """Send a message to the WebSocket."""
        if self.ws and self._connected:
            await self.ws.send(json.dumps(data))
    
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to OpenAI.
        
        Args:
            audio_data: PCM16 audio data (24kHz, mono)
        """
        if not self._connected:
            logger.warning("Cannot send audio: not connected")
            return
        
        # Base64 encode the audio
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        })
    
    async def commit_audio(self):
        """Commit the audio buffer to trigger a response."""
        await self._send({
            "type": "input_audio_buffer.commit"
        })
    
    async def send_text(self, text: str):
        """
        Send a text message (for testing without audio).
        
        Args:
            text: User's text message
        """
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text
                    }
                ]
            }
        })
        
        # Request a response
        await self._send({
            "type": "response.create"
        })
    
    async def cancel_response(self):
        """Cancel the current response (e.g., user interrupted)."""
        await self._send({
            "type": "response.cancel"
        })
    
    async def _receive_loop(self):
        """Main loop for receiving messages from OpenAI."""
        try:
            async for message in self.ws:
                await self._handle_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {e}")
            self._connected = False
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            if self.on_error:
                self.on_error(str(e))
    
    async def _handle_message(self, event: dict):
        """Handle an incoming event from OpenAI."""
        event_type = event.get("type", "")
        
        logger.debug(f"Received event: {event_type}")
        
        if event_type == "session.created":
            self.session_id = event.get("session", {}).get("id")
            logger.info(f"Session created: {self.session_id}")
            if self.on_session_created:
                self.on_session_created(self.session_id)
        
        elif event_type == "session.updated":
            logger.info("Session updated successfully")
        
        elif event_type == "response.audio.delta":
            # Audio chunk received
            audio_b64 = event.get("delta", "")
            if audio_b64 and self.on_audio_delta:
                self.on_audio_delta(audio_b64)
        
        elif event_type == "response.audio_transcript.delta":
            # Partial transcript of assistant's speech - accumulate it
            transcript = event.get("delta", "")
            if transcript:
                self._current_assistant_transcript += transcript
        
        elif event_type == "conversation.item.input_audio_transcription.completed":
            # User's speech transcription
            transcript = event.get("transcript", "")
            if transcript and self.on_transcript:
                self.on_transcript("user", transcript)
        
        elif event_type == "response.function_call_arguments.done":
            # Function call completed - execute the tool
            call_id = event.get("call_id")
            name = event.get("name")
            arguments = event.get("arguments", "{}")
            
            logger.info(f"Function call: {name} with args: {arguments}")
            
            try:
                args = json.loads(arguments)
                
                # Use sync_to_async for Django ORM queries
                from asgiref.sync import sync_to_async
                result = await sync_to_async(execute_voice_tool, thread_sensitive=True)(name, args)
                
                # Send function result back
                await self._send({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result)
                    }
                })
                
                # Request continuation
                await self._send({
                    "type": "response.create"
                })
                
            except Exception as e:
                logger.error(f"Function call error: {e}")
                await self._send({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({"error": str(e)})
                    }
                })
        
        elif event_type == "error":
            error = event.get("error", {})
            error_msg = error.get("message", "Unknown error")
            logger.error(f"OpenAI error: {error_msg}")
            if self.on_error:
                self.on_error(error_msg)
        
        elif event_type == "response.done":
            # Response completed - send the accumulated transcript
            if self._current_assistant_transcript and self.on_transcript:
                self.on_transcript("assistant", self._current_assistant_transcript)
            self._current_assistant_transcript = ""  # Reset for next response
            logger.debug("Response completed")
        
        elif event_type == "rate_limits.updated":
            # Rate limit info - just log it
            logger.debug(f"Rate limits: {event.get('rate_limits', [])}")
    
    async def disconnect(self):
        """Disconnect from OpenAI Realtime API."""
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        logger.info("Disconnected from OpenAI Realtime API")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to OpenAI."""
        return self._connected and self.ws is not None
