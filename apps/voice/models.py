"""
Voice session models for tracking voice agent interactions.
Supports Master Agent (platform-wide) and Shop Agents (shop-specific with role-based tools).
"""
import uuid
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


# Agent type choices - used across multiple models
AGENT_TYPE_CHOICES = [
    ('master', 'Master Agent'),
    ('shop', 'Shop Agent'),
]

# User role choices for shop agents
USER_ROLE_CHOICES = [
    ('customer', 'Customer'),
    ('client', 'Client/Owner'),
    ('staff', 'Staff Member'),
    ('guest', 'Guest'),
]


class VoiceSession(BaseModel):
    """
    Tracks a voice agent session.
    Sessions can span agent switches (master -> shop) with same session_id.
    """
    session_id = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4,
        help_text='Unique session identifier'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voice_sessions',
        help_text='Authenticated user (if any)'
    )
    
    # Agent tracking - which agent type is currently active
    agent_type = models.CharField(
        max_length=20,
        choices=AGENT_TYPE_CHOICES,
        default='master',
        help_text='Current agent type (master or shop)'
    )
    
    # Shop context - set when connected to shop agent
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voice_sessions',
        help_text='Shop for shop agent sessions'
    )
    
    # User role within the shop context
    user_role = models.CharField(
        max_length=20,
        choices=USER_ROLE_CHOICES,
        default='guest',
        help_text='User role for shop agent sessions'
    )
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('error', 'Error'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    total_interactions = models.IntegerField(default=0)
    total_duration_seconds = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)
    
    # OpenAI session tracking
    openai_session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='OpenAI Realtime session ID'
    )
    
    class Meta:
        db_table = 'voice_sessions'
        verbose_name = 'Voice Session'
        verbose_name_plural = 'Voice Sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['agent_type', 'status']),
        ]
    
    def __str__(self):
        agent = f"[{self.agent_type}]"
        shop = f" @ {self.shop.name}" if self.shop else ""
        return f"Voice Session {self.session_id[:8]} {agent}{shop} - {self.status}"


class VoiceCallLog(BaseModel):
    """
    Detailed log of each interaction in a voice session.
    Tracks agent type, user input, agent response, tool calls, and metrics.
    """
    session = models.ForeignKey(
        VoiceSession,
        on_delete=models.CASCADE,
        related_name='call_logs'
    )
    
    # Agent context at time of interaction
    agent_type = models.CharField(
        max_length=20,
        choices=AGENT_TYPE_CHOICES,
        help_text='Agent type that handled this interaction'
    )
    
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voice_call_logs',
        help_text='Shop context (for shop agent)'
    )
    
    user_role = models.CharField(
        max_length=20,
        choices=USER_ROLE_CHOICES,
        default='guest',
        help_text='User role during this interaction'
    )
    
    # Interaction content
    INTERACTION_TYPES = [
        ('user_speech', 'User Speech'),
        ('assistant_speech', 'Assistant Speech'),
        ('tool_call', 'Tool Call'),
        ('agent_switch', 'Agent Switch'),
        ('error', 'Error'),
    ]
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES
    )
    
    # Transcripts
    user_input = models.TextField(
        blank=True,
        help_text='Transcribed user speech'
    )
    agent_response = models.TextField(
        blank=True,
        help_text='Agent response text'
    )
    
    # Tool call details
    tool_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Name of tool called (if any)'
    )
    tool_input = models.JSONField(
        null=True,
        blank=True,
        help_text='Tool input parameters'
    )
    tool_output = models.JSONField(
        null=True,
        blank=True,
        help_text='Tool execution result'
    )
    tool_success = models.BooleanField(
        default=True,
        help_text='Whether tool execution succeeded'
    )
    
    # Metrics
    response_time_ms = models.IntegerField(
        default=0,
        help_text='Time to generate response in milliseconds'
    )
    tokens_used = models.IntegerField(
        default=0,
        help_text='Tokens consumed for this interaction'
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text='Error details if interaction failed'
    )
    
    class Meta:
        db_table = 'voice_call_logs'
        verbose_name = 'Voice Call Log'
        verbose_name_plural = 'Voice Call Logs'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['agent_type', 'interaction_type']),
            models.Index(fields=['shop', 'created_at']),
            models.Index(fields=['tool_name']),
        ]
    
    def __str__(self):
        return f"{self.interaction_type} [{self.agent_type}] - {self.session.session_id[:8]}"


class ShopVoiceAgent(BaseModel):
    """
    Shop-specific voice agent configuration.
    Created automatically when a Shop is created via Django signals.
    """
    shop = models.OneToOneField(
        'shops.Shop',
        on_delete=models.CASCADE,
        related_name='voice_agent',
        help_text='The shop this agent belongs to'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Whether the voice agent is active for this shop'
    )
    
    # Voice configuration
    VOICE_CHOICES = [
        ('alloy', 'Alloy'),
        ('echo', 'Echo'),
        ('fable', 'Fable'),
        ('onyx', 'Onyx'),
        ('nova', 'Nova'),
        ('shimmer', 'Shimmer'),
    ]
    voice = models.CharField(
        max_length=50,
        choices=VOICE_CHOICES,
        default='alloy',
        help_text='OpenAI voice for this agent'
    )
    
    # Custom prompts
    custom_greeting = models.TextField(
        blank=True,
        help_text='Optional custom greeting message'
    )
    custom_instructions = models.TextField(
        blank=True,
        help_text='Additional instructions for the agent (appended to base prompt)'
    )
    
    # Stats
    total_sessions = models.IntegerField(default=0)
    total_bookings_created = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'shop_voice_agents'
        verbose_name = 'Shop Voice Agent'
        verbose_name_plural = 'Shop Voice Agents'
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Voice Agent for {self.shop.name} ({status})"


# Keep VoiceInteraction for backwards compatibility (alias)
VoiceInteraction = VoiceCallLog
