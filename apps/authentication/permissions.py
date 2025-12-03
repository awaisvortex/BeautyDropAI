"""
Authentication permissions
"""
from rest_framework import permissions


class IsAuthenticatedUser(permissions.BasePermission):
    """
    Permission to check if user is authenticated
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to only allow owners to edit
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user
