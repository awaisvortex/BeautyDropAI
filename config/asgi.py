"""
ASGI config for salon booking system.
Supports HTTP and WebSocket connections for voice agent.
"""
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

# Initialize Django ASGI application early to ensure settings are loaded
django_asgi_app = get_asgi_application()

# Import routing after Django is initialized
from apps.voice.routing import websocket_urlpatterns

from channels.auth import AuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
