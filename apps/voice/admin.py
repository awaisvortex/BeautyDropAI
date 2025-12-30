from django.contrib import admin
from .models import VoiceSession, VoiceCallLog, ShopVoiceAgent


@admin.register(VoiceSession)
class VoiceSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'agent_type', 'shop', 'user_role', 'status', 
                    'total_interactions', 'started_at', 'ended_at']
    list_filter = ['status', 'agent_type', 'user_role', 'started_at']
    search_fields = ['session_id', 'user__email', 'shop__name']
    readonly_fields = ['session_id', 'started_at', 'created_at', 'updated_at']
    ordering = ['-started_at']
    raw_id_fields = ['user', 'shop']


@admin.register(VoiceCallLog)
class VoiceCallLogAdmin(admin.ModelAdmin):
    list_display = ['session', 'agent_type', 'interaction_type', 'tool_name', 
                    'tool_success', 'response_time_ms', 'created_at']
    list_filter = ['agent_type', 'interaction_type', 'tool_success', 'created_at']
    search_fields = ['session__session_id', 'user_input', 'agent_response', 'tool_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['session', 'shop']


@admin.register(ShopVoiceAgent)
class ShopVoiceAgentAdmin(admin.ModelAdmin):
    list_display = ['shop', 'is_active', 'voice', 'total_sessions', 'total_bookings_created']
    list_filter = ['is_active', 'voice']
    search_fields = ['shop__name']
    readonly_fields = ['total_sessions', 'total_bookings_created', 'created_at', 'updated_at']
    raw_id_fields = ['shop']

