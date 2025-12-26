"""
WebSocket URL routing for voice agent.
"""
from django.urls import re_path

from .consumers import VoiceConsumer

websocket_urlpatterns = [
    re_path(r'ws/voice/$', VoiceConsumer.as_asgi()),
]
