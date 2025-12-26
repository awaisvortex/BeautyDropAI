"""
Celery application configuration for BeautyDropAI.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('beautydropai')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    # Send booking reminders every hour
    # Checks for bookings that need 1-day or 1-hour reminders
    'send-booking-reminders': {
        'task': 'apps.notifications.tasks.send_booking_reminders_task',
        'schedule': crontab(minute=0),  # Run at the start of every hour
    },
    
    # Sync knowledge base to Pinecone every hour
    # Catches any items that failed real-time sync
    'sync-knowledge-base-hourly': {
        'task': 'agent.sync_knowledge_base',
        'schedule': crontab(minute=30),  # Run at 30 minutes past every hour
        'kwargs': {'full_sync': False},  # Incremental sync (only items needing resync)
    },
    
    # Full knowledge base sync daily at 3am
    # Complete sync to ensure data consistency
    'sync-knowledge-base-daily': {
        'task': 'agent.sync_knowledge_base',
        'schedule': crontab(hour=3, minute=0),  # Run at 3am daily
        'kwargs': {'full_sync': True},
    },
    
    # Cleanup deleted/inactive items weekly
    'cleanup-knowledge-base-weekly': {
        'task': 'agent.cleanup_knowledge_base',
        'schedule': crontab(hour=4, minute=0, day_of_week='sunday'),  # Sunday 4am
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
