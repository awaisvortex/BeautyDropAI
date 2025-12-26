"""
AI Agent models for chat sessions, messages, actions, and knowledge management.
"""
import uuid
from django.db import models
from apps.core.models import BaseModel


class ChatSession(BaseModel):
    """
    A chat session between user and AI agent.
    Each session maintains conversation context and history.
    """
    # User who owns this session (NULL for guest sessions)
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        to_field='clerk_user_id',
        null=True,
        blank=True,
        help_text='NULL for guest (unauthenticated) sessions'
    )
    
    # Session identifier (UUID)
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # User's role for context
    user_role = models.CharField(
        max_length=20,
        choices=[
            ('customer', 'Customer'),
            ('client', 'Shop Owner'),
            ('staff', 'Staff'),
        ],
        db_index=True
    )
    
    # Context tracking
    current_shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_sessions',
        help_text='Shop being discussed in this session'
    )
    
    # Session state
    is_active = models.BooleanField(default=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Summary for long conversations (AI-generated)
    summary = models.TextField(
        blank=True,
        help_text='AI-generated summary of older messages for context management'
    )
    
    # Stats
    message_count = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)
    
    # Metadata for debugging
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional session data (device, IP, user agent, etc.)'
    )
    
    class Meta:
        db_table = 'agent_chat_sessions'
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.session_id[:8]}... ({self.user_role})"
    
    def save(self, *args, **kwargs):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        super().save(*args, **kwargs)


class ChatMessage(BaseModel):
    """
    Individual message in a chat session.
    Stores both user and agent messages with full details for debugging.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
        ('tool', 'Tool Result'),
    ]
    
    # Parent session
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Message role
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)
    
    # Message content
    content = models.TextField()
    
    # For tool/function calls (when assistant requests tools)
    tool_calls = models.JSONField(
        null=True,
        blank=True,
        help_text='OpenAI tool_calls array if assistant requested tools'
    )
    
    # For tool results (response to a tool call)
    tool_call_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='ID of tool call this message responds to'
    )
    tool_name = models.CharField(
        max_length=100, 
        blank=True,
        db_index=True
    )
    
    # Token usage for this message
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    
    # OpenAI request/response tracking for debugging
    openai_request_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='OpenAI API request ID for debugging'
    )
    model_used = models.CharField(
        max_length=50,
        blank=True,
        help_text='OpenAI model used (e.g., gpt-4-turbo-preview)'
    )
    
    # Processing time for performance monitoring
    processing_time_ms = models.IntegerField(
        default=0,
        help_text='Time taken to generate response in milliseconds'
    )
    
    # Error tracking
    is_error = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'agent_chat_messages'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
            models.Index(fields=['is_error']),
        ]
    
    def __str__(self):
        preview = self.content[:50] if self.content else "(empty)"
        return f"{self.role}: {preview}..."


class AgentAction(BaseModel):
    """
    Audit log for all actions/tool executions by the agent.
    Used for debugging, analytics, and auditing.
    """
    ACTION_TYPES = [
        # Booking actions
        ('booking_create', 'Create Booking'),
        ('booking_cancel', 'Cancel Booking'),
        ('booking_reschedule', 'Reschedule Booking'),
        ('booking_confirm', 'Confirm Booking'),
        ('booking_complete', 'Complete Booking'),
        ('booking_list', 'List Bookings'),
        # Query actions
        ('shop_search', 'Search Shops'),
        ('shop_info', 'Get Shop Info'),
        ('service_list', 'List Services'),
        ('service_info', 'Get Service Info'),
        ('availability_check', 'Check Availability'),
        ('schedule_info', 'Get Schedule'),
        ('staff_list', 'List Staff'),
        ('staff_info', 'Get Staff Info'),
        # Owner actions
        ('staff_reassign', 'Reassign Staff'),
        ('slot_block', 'Block Time Slot'),
        ('slot_unblock', 'Unblock Time Slot'),
        ('holiday_add', 'Add Holiday'),
        ('stats_query', 'Query Statistics'),
    ]
    
    # Link to message that triggered this action
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    
    # Action type
    action_type = models.CharField(
        max_length=50, 
        choices=ACTION_TYPES,
        db_index=True
    )
    
    # Input/Output for debugging
    input_params = models.JSONField(
        help_text='Tool input parameters'
    )
    output_result = models.JSONField(
        null=True,
        blank=True,
        help_text='Tool output result'
    )
    
    # Status tracking
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.TextField(blank=True)
    execution_time_ms = models.IntegerField(default=0)
    
    # Related objects for quick queries
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_actions'
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_actions'
    )
    
    class Meta:
        db_table = 'agent_actions'
        verbose_name = 'Agent Action'
        verbose_name_plural = 'Agent Actions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action_type', 'success']),
            models.Index(fields=['created_at']),
            models.Index(fields=['message', 'action_type']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.action_type} - {self.created_at}"


class KnowledgeDocument(BaseModel):
    """
    Tracks documents synced to Pinecone vector database.
    Used for managing the knowledge base.
    """
    DOC_TYPES = [
        ('shop', 'Shop'),
        ('service', 'Service'),
        ('faq', 'FAQ'),
    ]
    
    doc_type = models.CharField(
        max_length=20, 
        choices=DOC_TYPES,
        db_index=True
    )
    
    # Reference to source (one should be set based on doc_type)
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='knowledge_docs'
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='knowledge_docs'
    )
    
    # Pinecone tracking
    pinecone_id = models.CharField(max_length=255, unique=True, db_index=True)
    pinecone_namespace = models.CharField(max_length=50, db_index=True)
    
    # Content that was embedded
    content_text = models.TextField(
        help_text='The text that was embedded and stored'
    )
    metadata_json = models.JSONField(
        help_text='Metadata stored with the vector in Pinecone'
    )
    
    # Sync tracking
    last_synced_at = models.DateTimeField()
    needs_resync = models.BooleanField(default=False, db_index=True)
    sync_error = models.TextField(blank=True)
    
    class Meta:
        db_table = 'agent_knowledge_docs'
        verbose_name = 'Knowledge Document'
        verbose_name_plural = 'Knowledge Documents'
        indexes = [
            models.Index(fields=['doc_type', 'shop']),
            models.Index(fields=['pinecone_id']),
            models.Index(fields=['needs_resync']),
        ]
    
    def __str__(self):
        if self.shop:
            return f"{self.doc_type}: {self.shop.name}"
        elif self.service:
            return f"{self.doc_type}: {self.service.name}"
        return f"{self.doc_type}: {self.pinecone_id[:20]}"
