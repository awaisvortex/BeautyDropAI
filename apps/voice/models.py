"""
Voice session models for tracking voice agent interactions.
"""
import uuid
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class VoiceSession(BaseModel):
    """
    Tracks a voice agent session.
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
    
    def __str__(self):
        return f"Voice Session {self.session_id[:8]} - {self.status}"


class VoiceInteraction(BaseModel):
    """
    Logs individual interactions within a voice session.
    """
    session = models.ForeignKey(
        VoiceSession,
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    
    INTERACTION_TYPES = [
        ('user_speech', 'User Speech'),
        ('assistant_speech', 'Assistant Speech'),
        ('function_call', 'Function Call'),
        ('error', 'Error'),
    ]
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES
    )
    
    # Content (transcription or function details)
    content = models.TextField(blank=True)
    
    # For function calls
    function_name = models.CharField(max_length=100, blank=True)
    function_args = models.JSONField(null=True, blank=True)
    function_result = models.JSONField(null=True, blank=True)
    
    # Timing
    duration_ms = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'voice_interactions'
        verbose_name = 'Voice Interaction'
        verbose_name_plural = 'Voice Interactions'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.interaction_type} in {self.session.session_id[:8]}"
