"""
URL routes for notifications API.
"""
from django.urls import path
from apps.notifications.views import (
    NotificationListView,
    NotificationCountView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
    NotificationPreferenceView,
    NotificationDeleteView,
    ClearAllNotificationsView,
    TestEmailView
)

app_name = 'notifications'

urlpatterns = [
    # Notification listing and management
    path('', NotificationListView.as_view(), name='notification-list'),
    path('count/', NotificationCountView.as_view(), name='notification-count'),
    path('mark-read/', MarkNotificationReadView.as_view(), name='mark-read'),
    path('mark-all-read/', MarkAllNotificationsReadView.as_view(), name='mark-all-read'),
    path('clear-all/', ClearAllNotificationsView.as_view(), name='clear-all'),
    path('<uuid:pk>/', NotificationDeleteView.as_view(), name='notification-delete'),
    
    # Notification preferences
    path('preferences/', NotificationPreferenceView.as_view(), name='preferences'),
    
    # Testing
    path('test-email/', TestEmailView.as_view(), name='test-email'),
]
