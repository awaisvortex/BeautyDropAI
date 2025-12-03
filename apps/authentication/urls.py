"""
Authentication URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    # User profile endpoints (Clerk-authenticated)
    path('me/', views.get_current_user, name='current-user'),
    path('profile/update/', views.update_profile, name='update-profile'),
    path('set-role/', views.set_user_role, name='set-role'),
    path('health/', views.health_check, name='health-check'),
]
