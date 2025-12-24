"""
AI Agent API views.
"""
import uuid
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from .models import ChatSession, ChatMessage
from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatSessionSerializer,
    ChatSessionListSerializer,
)

logger = logging.getLogger(__name__)


class AgentViewSet(viewsets.ViewSet):
    """
    AI Agent endpoints for chat interactions.
    
    Provides chat functionality for customers, shop owners, and staff.
    Each user role gets tailored context and capabilities.
    """
    permission_classes = [IsAuthenticated]
    
    def _get_user_role(self, user):
        """Determine user's role for context."""
        if hasattr(user, 'customer_profile') and user.customer_profile:
            return 'customer'
        elif hasattr(user, 'client_profile') and user.client_profile:
            return 'client'
        elif hasattr(user, 'staff_profile') and user.staff_profile:
            return 'staff'
        return user.role if hasattr(user, 'role') else 'customer'
    
    @extend_schema(
        summary="Chat with AI Agent",
        description="""
        Send a message to the AI assistant and receive a response.
        
        The agent can:
        - **Customers**: Search shops, check availability, book/cancel appointments
        - **Shop Owners**: Manage bookings, view analytics, manage staff
        - **Staff**: View schedule, complete bookings
        
        Include `session_id` to continue an existing conversation.
        Omit `session_id` to start a new conversation.
        """,
        request=ChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=['AI Agent']
    )
    @action(detail=False, methods=['post'])
    def chat(self, request):
        """Process a chat message and return AI response."""
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user_role = self._get_user_role(user)
        message = serializer.validated_data['message']
        session_id = serializer.validated_data.get('session_id')
        
        # Get or create session
        if session_id:
            try:
                session = ChatSession.objects.get(
                    session_id=session_id,
                    user=user
                )
            except ChatSession.DoesNotExist:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                user=user,
                session_id=session_id,
                user_role=user_role
            )
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message
        )
        
        # TODO: Implement agent controller to process message
        # For now, return placeholder response
        try:
            from .services.agent_controller import AgentController
            controller = AgentController(user, session)
            result = controller.process_message(message)
            
            # Save assistant message
            assistant_message = ChatMessage.objects.create(
                session=session,
                role='assistant',
                content=result['response'],
                prompt_tokens=result.get('prompt_tokens', 0),
                completion_tokens=result.get('completion_tokens', 0),
                openai_request_id=result.get('request_id', ''),
                model_used=result.get('model', ''),
                processing_time_ms=result.get('processing_time_ms', 0)
            )
            
            # Update session stats
            session.message_count = session.messages.count()
            session.total_tokens_used += result.get('prompt_tokens', 0) + result.get('completion_tokens', 0)
            session.save(update_fields=['message_count', 'total_tokens_used', 'updated_at'])
            
            return Response({
                'response': result['response'],
                'session_id': session_id,
                'message_id': str(assistant_message.id),
                'actions_taken': result.get('actions_taken', []),
                'tokens_used': {
                    'prompt': result.get('prompt_tokens', 0),
                    'completion': result.get('completion_tokens', 0)
                }
            })
            
        except ImportError:
            # Agent controller not yet implemented
            logger.warning("AgentController not implemented, returning placeholder")
            
            assistant_message = ChatMessage.objects.create(
                session=session,
                role='assistant',
                content="I'm currently being set up. Please check back soon!"
            )
            
            session.message_count = session.messages.count()
            session.save(update_fields=['message_count', 'updated_at'])
            
            return Response({
                'response': "I'm currently being set up. Please check back soon!",
                'session_id': session_id,
                'message_id': str(assistant_message.id),
                'actions_taken': [],
                'tokens_used': {'prompt': 0, 'completion': 0}
            })
        
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            
            # Save error message
            ChatMessage.objects.create(
                session=session,
                role='assistant',
                content="I encountered an error processing your request. Please try again.",
                is_error=True,
                error_message=str(e)
            )
            
            return Response(
                {'error': 'Failed to process message'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="List chat sessions",
        description="Get a list of the user's recent chat sessions.",
        responses={200: ChatSessionListSerializer(many=True)},
        tags=['AI Agent']
    )
    @action(detail=False, methods=['get'])
    def sessions(self, request):
        """List user's chat sessions."""
        sessions = ChatSession.objects.filter(
            user=request.user
        ).order_by('-updated_at')[:50]
        
        serializer = ChatSessionListSerializer(sessions, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get chat session",
        description="Retrieve a specific chat session with all messages.",
        responses={
            200: ChatSessionSerializer,
            404: OpenApiResponse(description="Session not found"),
        },
        tags=['AI Agent']
    )
    @action(detail=False, methods=['get'], url_path='sessions/(?P<session_id>[^/.]+)')
    def get_session(self, request, session_id=None):
        """Get a specific chat session with messages."""
        try:
            session = ChatSession.objects.prefetch_related('messages').get(
                session_id=session_id,
                user=request.user
            )
            serializer = ChatSessionSerializer(session)
            return Response(serializer.data)
        except ChatSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="End chat session",
        description="Mark a chat session as inactive/ended.",
        responses={
            200: OpenApiResponse(description="Session ended successfully"),
            404: OpenApiResponse(description="Session not found"),
        },
        tags=['AI Agent']
    )
    @action(detail=False, methods=['post'], url_path='sessions/(?P<session_id>[^/.]+)/end')
    def end_session(self, request, session_id=None):
        """End a chat session."""
        try:
            session = ChatSession.objects.get(
                session_id=session_id,
                user=request.user
            )
            session.is_active = False
            session.ended_at = timezone.now()
            session.save(update_fields=['is_active', 'ended_at', 'updated_at'])
            
            return Response({'message': 'Session ended successfully'})
        except ChatSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Delete chat session",
        description="Delete a chat session and all its messages.",
        responses={
            204: OpenApiResponse(description="Session deleted"),
            404: OpenApiResponse(description="Session not found"),
        },
        tags=['AI Agent']
    )
    @action(detail=False, methods=['delete'], url_path='sessions/(?P<session_id>[^/.]+)')
    def delete_session(self, request, session_id=None):
        """Delete a chat session."""
        try:
            session = ChatSession.objects.get(
                session_id=session_id,
                user=request.user
            )
            session.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ChatSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
