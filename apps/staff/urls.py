"""
Staff URL configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffMemberViewSet
from .staff_views import StaffDashboardViewSet

router = DefaultRouter()
router.register(r'', StaffMemberViewSet, basename='staff')

# Separate router for dashboard to avoid conflicts
dashboard_router = DefaultRouter()
dashboard_router.register(r'dashboard', StaffDashboardViewSet, basename='staff-dashboard')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(dashboard_router.urls)),
]

