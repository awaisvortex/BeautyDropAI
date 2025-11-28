"""
Schedules URL patterns
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'schedules'

router = DefaultRouter()
router.register(r'', views.ShopScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),
]
