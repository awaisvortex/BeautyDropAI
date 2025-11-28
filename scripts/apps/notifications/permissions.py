"""
Notifications permissions
"""
from rest_framework import permissions


class IsNotificationOwner(permissions.BasePermission):
    """
    Permission to check if user owns the notification
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
