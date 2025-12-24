"""
Serializers for AI Agent API.
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from .models import ChatSession, ChatMessage, AgentAction


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Start new conversation',
            summary='Start a NEW chat (no session_id)',
            description=(
                'Send a message WITHOUT session_id to start a brand new conversation. '
                'The response will include a new session_id that you should save and use '
                'for subsequent messages to continue this conversation.'
            ),
            value={
                'message': 'Find me a salon that does haircuts near downtown'
            },
            request_only=True
        ),
        OpenApiExample(
            'Continue conversation',
            summary='CONTINUE existing chat (with session_id)',
            description=(
                'Include the session_id from a previous response to continue that conversation. '
                'This allows the AI to remember the conversation history and context, '
                'so you can have multi-turn conversations like "book me for 2pm" after '
                'asking about available times.'
            ),
            value={
                'message': 'What times are available tomorrow?',
                'session_id': '550e8400-e29b-41d4-a716-446655440000'
            },
            request_only=True
        ),
    ]
)
class ChatRequestSerializer(serializers.Serializer):
    """Request serializer for chat endpoint."""
    message = serializers.CharField(
        max_length=4000,
        help_text='User message to send to the AI agent (max 4000 characters)'
    )
    session_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text=(
            'UUID session ID to continue an existing conversation. '
            'The session_id maintains conversation history and context, allowing the AI to remember '
            'previous messages in the chat. Omit this field to start a NEW conversation. '
            'Include the session_id from a previous response to CONTINUE that conversation.'
        )
    )


class TokensUsedSerializer(serializers.Serializer):
    """Serializer for token usage."""
    prompt = serializers.IntegerField(help_text='Number of prompt tokens used')
    completion = serializers.IntegerField(help_text='Number of completion tokens used')


class ActionTakenSerializer(serializers.Serializer):
    """Serializer for actions taken by the agent."""
    action_type = serializers.CharField(help_text='Type of action (e.g., search_shops, create_booking)')
    success = serializers.BooleanField(help_text='Whether the action succeeded')
    details = serializers.DictField(
        required=False,
        help_text='Action-specific details and results'
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Simple response',
            summary='Simple text response',
            value={
                'response': 'I found 3 salons near downtown that offer haircuts. Would you like me to show you the available times?',
                'session_id': '550e8400-e29b-41d4-a716-446655440000',
                'message_id': '7c9e6679-7425-40de-944b-e07fc1f90ae7',
                'actions_taken': [],
                'tokens_used': {'prompt': 450, 'completion': 85}
            },
            response_only=True
        ),
        OpenApiExample(
            'Response with actions',
            summary='Response after executing tools',
            value={
                'response': 'I found 3 salons near downtown:\n\n1. **Andy & Wendi** - 4.8★ (25 reviews)\n2. **Test Saloon** - 4.5★ (12 reviews)\n3. **NEW SALOON** - 4.2★ (8 reviews)\n\nWould you like to see available times for any of these?',
                'session_id': '550e8400-e29b-41d4-a716-446655440000',
                'message_id': '7c9e6679-7425-40de-944b-e07fc1f90ae7',
                'actions_taken': [
                    {
                        'action_type': 'search_shops',
                        'success': True,
                        'details': {'count': 3, 'query': 'haircuts near downtown'}
                    }
                ],
                'tokens_used': {'prompt': 520, 'completion': 150}
            },
            response_only=True
        ),
        OpenApiExample(
            'Booking confirmation',
            summary='After creating a booking',
            value={
                'response': 'Your haircut appointment has been booked!\n\n📅 **December 25, 2024 at 2:00 PM**\n🏪 Andy & Wendi\n💇 Haircut ($35)\n\nYou will receive a confirmation email shortly.',
                'session_id': '550e8400-e29b-41d4-a716-446655440000',
                'message_id': '7c9e6679-7425-40de-944b-e07fc1f90ae7',
                'actions_taken': [
                    {
                        'action_type': 'create_booking',
                        'success': True,
                        'details': {
                            'booking_id': '123e4567-e89b-12d3-a456-426614174000',
                            'shop': 'Andy & Wendi',
                            'service': 'Haircut',
                            'datetime': '2024-12-25T14:00:00'
                        }
                    }
                ],
                'tokens_used': {'prompt': 680, 'completion': 95}
            },
            response_only=True
        ),
    ]
)
class ChatResponseSerializer(serializers.Serializer):
    """Response serializer for chat endpoint."""
    response = serializers.CharField(
        help_text='AI agent response message'
    )
    session_id = serializers.CharField(
        help_text='UUID session ID for continuing this conversation'
    )
    message_id = serializers.UUIDField(
        help_text='Unique ID of this assistant message'
    )
    actions_taken = ActionTakenSerializer(
        many=True, 
        required=False,
        help_text='List of tool actions executed by the agent'
    )
    tokens_used = TokensUsedSerializer(
        required=False,
        help_text='Token usage for this request'
    )


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""
    tokens_total = serializers.SerializerMethodField(
        help_text='Total tokens (prompt + completion)'
    )
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'role', 'content', 'tool_name', 'is_error', 'error_message',
            'tokens_total', 'processing_time_ms', 'created_at'
        ]
    
    def get_tokens_total(self, obj):
        return obj.prompt_tokens + obj.completion_tokens


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Session with messages',
            value={
                'id': '123e4567-e89b-12d3-a456-426614174000',
                'session_id': '550e8400-e29b-41d4-a716-446655440000',
                'user_email': 'customer@example.com',
                'user_role': 'customer',
                'shop_name': None,
                'is_active': True,
                'message_count': 4,
                'total_tokens_used': 1250,
                'summary': '',
                'created_at': '2024-12-24T10:00:00Z',
                'updated_at': '2024-12-24T10:05:00Z',
                'messages': [
                    {
                        'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7',
                        'role': 'user',
                        'content': 'Find me salons near downtown',
                        'tool_name': '',
                        'is_error': False,
                        'error_message': '',
                        'tokens_total': 0,
                        'processing_time_ms': 0,
                        'created_at': '2024-12-24T10:00:00Z'
                    },
                    {
                        'id': '8d0f7780-8536-41ef-a55c-f18gd2g01bf8',
                        'role': 'assistant',
                        'content': 'I found 3 salons near downtown...',
                        'tool_name': '',
                        'is_error': False,
                        'error_message': '',
                        'tokens_total': 535,
                        'processing_time_ms': 1250,
                        'created_at': '2024-12-24T10:00:02Z'
                    }
                ]
            },
            response_only=True
        ),
    ]
)
class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat session with messages."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    user_email = serializers.CharField(
        source='user.email', 
        read_only=True,
        help_text='Email of the session owner'
    )
    shop_name = serializers.CharField(
        source='current_shop.name', 
        read_only=True, 
        allow_null=True,
        help_text='Current shop being discussed (if any)'
    )
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'session_id', 'user_email', 'user_role', 'shop_name',
            'is_active', 'message_count', 'total_tokens_used', 
            'summary', 'created_at', 'updated_at', 'messages'
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Session list',
            value=[
                {
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'session_id': '550e8400-e29b-41d4-a716-446655440000',
                    'user_role': 'customer',
                    'is_active': True,
                    'message_count': 8,
                    'last_message_preview': 'Your booking has been confirmed for tomorrow at 2pm...',
                    'created_at': '2024-12-24T10:00:00Z',
                    'updated_at': '2024-12-24T10:15:00Z'
                },
                {
                    'id': '456e7890-f12g-34h5-i678-901234567890',
                    'session_id': '660f9511-f30c-52e5-b827-557766551111',
                    'user_role': 'customer',
                    'is_active': False,
                    'message_count': 3,
                    'last_message_preview': 'Thanks for using BeautyDrop! Have a great day!',
                    'created_at': '2024-12-23T14:00:00Z',
                    'updated_at': '2024-12-23T14:10:00Z'
                }
            ],
            response_only=True
        ),
    ]
)
class ChatSessionListSerializer(serializers.ModelSerializer):
    """Serializer for listing chat sessions (without messages)."""
    last_message_preview = serializers.SerializerMethodField(
        help_text='Preview of the last assistant message'
    )
    
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
    shop_name = serializers.CharField(
        source='shop.name', 
        read_only=True, 
        allow_null=True,
        help_text='Name of the shop involved in this action'
    )
    
    class Meta:
        model = AgentAction
        fields = [
            'id', 'action_type', 'input_params', 'output_result',
            'success', 'error_message', 'execution_time_ms',
            'shop_name', 'created_at'
        ]
