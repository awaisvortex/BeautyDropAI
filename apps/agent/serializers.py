"""
Serializers for AI Agent API.
"""
from rest_framework import serializers
from .models import ChatSession, ChatMessage, AgentAction


class ChatRequestSerializer(serializers.Serializer):
    """Request serializer for chat endpoint."""
    message = serializers.CharField(
        max_length=4000,
        help_text='User message to send to the AI agent'
    )
    session_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text='Session ID to continue existing conversation. Omit to start new session.'
    )


class ActionTakenSerializer(serializers.Serializer):
    """Serializer for actions taken by the agent."""
    action_type = serializers.CharField()
    success = serializers.BooleanField()
    details = serializers.DictField(required=False)


class ChatResponseSerializer(serializers.Serializer):
    """Response serializer for chat endpoint."""
    response = serializers.CharField(help_text='AI agent response')
    session_id = serializers.CharField(help_text='Session ID for continuing conversation')
    message_id = serializers.UUIDField(help_text='ID of the assistant message')
    actions_taken = ActionTakenSerializer(many=True, required=False)
    tokens_used = serializers.DictField(required=False)


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""
    tokens_total = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'role', 'content', 'tool_name', 'is_error', 'error_message',
            'tokens_total', 'processing_time_ms', 'created_at'
        ]
    
    def get_tokens_total(self, obj):
        return obj.prompt_tokens + obj.completion_tokens


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat session with messages."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    shop_name = serializers.CharField(source='current_shop.name', read_only=True, allow_null=True)
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user_email', 'user_role', 'shop_name',
            'is_active', 'message_count', 'total_tokens_used', 
            'summary', 'created_at', 'updated_at', 'messages'
        ]


class ChatSessionListSerializer(serializers.ModelSerializer):
    """Serializer for listing chat sessions (without messages)."""
    last_message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user_role', 'is_active', 
            'message_count', 'last_message_preview', 'created_at', 'updated_at'
        ]
    
    def get_last_message_preview(self, obj):
        last_msg = obj.messages.filter(role='assistant').order_by('-created_at').first()
        if last_msg:
            return last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content
        return None


class AgentActionSerializer(serializers.ModelSerializer):
    """Serializer for agent actions."""
    shop_name = serializers.CharField(source='shop.name', read_only=True, allow_null=True)
    
    class Meta:
        model = AgentAction
        fields = [
            'id', 'action_type', 'input_params', 'output_result',
            'success', 'error_message', 'execution_time_ms',
            'shop_name', 'created_at'
        ]
