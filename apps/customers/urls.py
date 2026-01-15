"""
URL configuration for customers app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'customers'

router = DefaultRouter()
router.register(r'', views.CustomerViewSet, basename='customer')

urlpatterns = router.urls
