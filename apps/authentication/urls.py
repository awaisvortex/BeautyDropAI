"""
Authentication URL Configuration
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, extend_schema_view
from . import views
from . import jwt_views

# Custom TokenRefreshView with proper schema
@extend_schema_view(
    post=extend_schema(
        summary="Refresh JWT token",
        description="Get a new access token using refresh token",
        tags=['Authentication - Public']
    )
)
class CustomTokenRefreshView(TokenRefreshView):
    pass

urlpatterns = [
    # User profile endpoints
    path('me/', views.get_current_user, name='current-user'),
    path('profile/update/', views.update_profile, name='update-profile'),
    path('set-role/', views.set_user_role, name='set-role'),
    path('health/', views.health_check, name='health-check'),
    
    # JWT Authentication endpoints
    path('register/', jwt_views.register, name='register'),
    path('login/', jwt_views.login, name='login'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('verify/', jwt_views.verify_token, name='verify-token'),
    path('logout/', jwt_views.logout, name='logout'),
    path('change-password/', jwt_views.change_password, name='change-password'),
]
