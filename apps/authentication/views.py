"""
Authentication views
"""
from datetime import datetime
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import User
from .serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    UserRegistrationSerializer,
    HealthCheckSerializer
)


@extend_schema(
    summary="Get current user",
    description="Retrieve the currently authenticated user's profile",
    responses={
        200: UserSerializer,
        401: OpenApiResponse(description="Unauthorized")
    },
    tags=['Authentication']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current authenticated user
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@extend_schema(
    summary="Update user profile",
    description="Update the current user's profile information",
    request=UserProfileUpdateSerializer,
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description="Bad Request"),
        401: OpenApiResponse(description="Unauthorized")
    },
    tags=['Authentication']
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user profile
    """
    serializer = UserProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=request.method == 'PATCH'
    )
    
    if serializer.is_valid():
        serializer.save()
        user_serializer = UserSerializer(request.user)
        return Response(user_serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Set user role",
    description="Set user role as either 'client' (salon owner) or 'customer'. Can only be set once.",
    request=UserRegistrationSerializer,
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description="Bad Request - Role already set or invalid"),
        401: OpenApiResponse(description="Unauthorized")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_user_role(request):
    """
    Set user role (client or customer) - only allowed once
    """
    # Check if role is already set
    if request.user.role and request.user.role != 'customer':
        return Response(
            {'error': 'Role already set and cannot be changed'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.update_user_role(request.user)
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Health check",
    description="Check API health status including database and cache connectivity",
    responses={200: HealthCheckSerializer},
    tags=['System']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint
    """
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        cache_status = "healthy" if cache.get('health_check') == 'ok' else "unhealthy"
    except Exception as e:
        cache_status = f"unhealthy: {str(e)}"
    
    return Response({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'cache': cache_status
    })
