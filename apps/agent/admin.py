"""
Admin configuration for AI Agent models.
Provides debugging and monitoring interface.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import ChatSession, ChatMessage, AgentAction, KnowledgeDocument


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['role', 'content', 'tool_name', 'tokens_used', 'is_error', 'created_at']
    fields = ['role', 'content', 'tool_name', 'tokens_used', 'is_error', 'created_at']
    ordering = ['created_at']
    
    @admin.display(description='Tokens')
    def tokens_used(self, obj):
        return obj.prompt_tokens + obj.completion_tokens
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id_short', 'user_email', 'user_role', 'message_count', 
                    'total_tokens_used', 'is_active', 'created_at']
    list_filter = ['user_role', 'is_active', 'created_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'message_count', 'total_tokens_used', 'created_at', 'updated_at']
    inlines = [ChatMessageInline]
    
    @admin.display(description='Session ID')
    def session_id_short(self, obj):
        return obj.session_id[:12] + '...'
    
    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_short', 'role', 'content_preview', 'tool_name', 
                    'tokens_total', 'is_error', 'processing_time_ms', 'created_at']
    list_filter = ['role', 'is_error', 'tool_name', 'created_at']
    search_fields = ['content', 'session__session_id', 'error_message']
    readonly_fields = ['session', 'role', 'content', 'tool_calls', 'tool_call_id', 
                       'tool_name', 'prompt_tokens', 'completion_tokens', 'openai_request_id',
                       'model_used', 'processing_time_ms', 'is_error', 'error_message', 
                       'created_at', 'updated_at']
    
    @admin.display(description='Session')
    def session_short(self, obj):
        return obj.session.session_id[:8] + '...'
    
    @admin.display(description='Content')
    def content_preview(self, obj):
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    
    @admin.display(description='Tokens')
    def tokens_total(self, obj):
        return obj.prompt_tokens + obj.completion_tokens


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'action_type', 'success_icon', 'shop_name', 'booking_id',
                    'execution_time_ms', 'created_at']
    list_filter = ['action_type', 'success', 'created_at']
    search_fields = ['input_params', 'output_result', 'error_message']
    readonly_fields = ['message', 'action_type', 'input_params', 'output_result',
                       'success', 'error_message', 'execution_time_ms', 'shop', 'booking',
                       'created_at', 'updated_at']
    
    @admin.display(description='Status')
    def success_icon(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    
    @admin.display(description='Shop')
    def shop_name(self, obj):
        return obj.shop.name if obj.shop else '-'
    
    @admin.display(description='Booking')
    def booking_id(self, obj):
        return str(obj.booking.id)[:8] if obj.booking else '-'


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'doc_type', 'source_name', 'pinecone_namespace', 
                    'needs_resync', 'last_synced_at']
    list_filter = ['doc_type', 'pinecone_namespace', 'needs_resync']
    search_fields = ['pinecone_id', 'content_text', 'shop__name', 'service__name']
    readonly_fields = ['pinecone_id', 'pinecone_namespace', 'content_text', 
                       'metadata_json', 'last_synced_at', 'sync_error']
    
    @admin.display(description='Source')
    def source_name(self, obj):
        if obj.shop:
            return f"Shop: {obj.shop.name}"
        elif obj.service:
            return f"Service: {obj.service.name}"
        return '-'
