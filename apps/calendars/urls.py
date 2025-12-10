"""
URL configuration for Calendar integration API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CalendarViewSet

router = DefaultRouter()
router.register(r'', CalendarViewSet, basename='calendars')

urlpatterns = [
    path('', include(router.urls)),
]
