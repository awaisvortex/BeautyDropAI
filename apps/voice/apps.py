from django.apps import AppConfig


class VoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voice'
    verbose_name = 'Voice Agent'
    
    def ready(self):
        # Import signals to register them
        from . import signals  # noqa: F401

