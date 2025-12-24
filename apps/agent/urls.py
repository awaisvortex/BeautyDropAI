"""
URL configuration for AI Agent.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'agent'

router = DefaultRouter()
router.register(r'', views.AgentViewSet, basename='agent')

urlpatterns = router.urls
