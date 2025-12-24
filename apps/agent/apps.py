from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agent'
    verbose_name = 'AI Agent'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.agent.signals  # noqa: F401
        except ImportError:
            pass
