"""
WebSocket URL routing for voice agent.
Supports Master Agent (platform-wide) and Shop Agents (shop-specific).
"""
from django.urls import re_path

from .consumers import VoiceConsumer

websocket_urlpatterns = [
    # Master agent - home/browse pages
    re_path(r'ws/voice/$', VoiceConsumer.as_asgi()),
    
    # Shop agent - direct connection from shop page
    # shop_id is a UUID
    re_path(r'ws/voice/shop/(?P<shop_id>[0-9a-f-]+)/$', VoiceConsumer.as_asgi()),
]

