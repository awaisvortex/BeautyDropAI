"""
URL routes for notifications API.
With Firebase Cloud Messaging integration.
"""
from django.urls import path
from apps.notifications.views import (
    NotificationPreferenceView,
    TestEmailView,
    FCMTokenView,
    NotificationListView,
    NotificationCountView,
    NotificationMarkReadView,
    DeleteNotificationView,
)

app_name = 'notifications'

urlpatterns = [
    # In-app notifications
    path('', NotificationListView.as_view(), name='list'),
    path('count/', NotificationCountView.as_view(), name='count'),
    path('mark-read/', NotificationMarkReadView.as_view(), name='mark-read'),
    path('<uuid:pk>/', DeleteNotificationView.as_view(), name='delete'),

    # FCM device token management
    path('fcm-token/', FCMTokenView.as_view(), name='fcm-token'),
    
    # Notification preferences (email + push settings)
    path('preferences/', NotificationPreferenceView.as_view(), name='preferences'),
    
    # Testing
    path('test-email/', TestEmailView.as_view(), name='test-email'),
]
