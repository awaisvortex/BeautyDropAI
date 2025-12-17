"""
URL routes for notifications API.
With Firebase Cloud Messaging integration.
"""
from django.urls import path
from apps.notifications.views import (
    NotificationPreferenceView,
    TestEmailView,
    FCMTokenView,
)

app_name = 'notifications'

urlpatterns = [
    # FCM device token management
    path('fcm-token/', FCMTokenView.as_view(), name='fcm-token'),
    
    # Notification preferences (email + push settings)
    path('preferences/', NotificationPreferenceView.as_view(), name='preferences'),
    
    # Testing
    path('test-email/', TestEmailView.as_view(), name='test-email'),
]
