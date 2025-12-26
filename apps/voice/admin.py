from django.contrib import admin
from .models import VoiceSession, VoiceInteraction


@admin.register(VoiceSession)
class VoiceSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'status', 'total_interactions', 'started_at', 'ended_at']
    list_filter = ['status', 'started_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'started_at', 'created_at', 'updated_at']
    ordering = ['-started_at']


@admin.register(VoiceInteraction)
class VoiceInteractionAdmin(admin.ModelAdmin):
    list_display = ['session', 'interaction_type', 'function_name', 'duration_ms', 'created_at']
    list_filter = ['interaction_type', 'created_at']
    search_fields = ['session__session_id', 'content', 'function_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
