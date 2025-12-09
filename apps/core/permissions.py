"""
Custom permissions for Beauty Drop AI
"""
from rest_framework import permissions


class IsClient(permissions.BasePermission):
    """Permission check for salon owners (clients)"""
    message = "Only salon owners can perform this action"
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'client'
        )


class IsCustomer(permissions.BasePermission):
    """Permission check for customers"""
    message = "Only customers can perform this action"
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'customer'
        )


class IsStaff(permissions.BasePermission):
    """Permission check for staff members"""
    message = "Only staff members can perform this action"
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'staff'
        )


class IsShopOwner(permissions.BasePermission):
    """Permission check for shop ownership"""
    message = "You do not have permission to access this shop"
    
    def has_object_permission(self, request, view, obj):
        # Check if user is client and owns the shop
        if not request.user.is_authenticated or request.user.role != 'client':
            return False
        
        # Handle different object types
        if hasattr(obj, 'client'):
            # Direct shop object
            return obj.client.user == request.user
        elif hasattr(obj, 'shop'):
            # Objects that belong to a shop (services, schedules, etc.)
            return obj.shop.client.user == request.user
        elif hasattr(obj, 'schedule'):
            # Time slots
            return obj.schedule.shop.client.user == request.user
        
        return False


class IsClientOrReadOnly(permissions.BasePermission):
    """Allow clients to edit, others to read"""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role == 'client'


class IsClientOrStaff(permissions.BasePermission):
    """Permission for actions that both clients and staff can perform"""
    message = "Only salon owners or staff members can perform this action"
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['client', 'staff']
        )


class IsBookingOwner(permissions.BasePermission):
    """Permission check for booking ownership"""
    message = "You do not have permission to access this booking"
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # Customers can access their own bookings
        if request.user.role == 'customer':
            return obj.customer.user == request.user
        
        # Clients can access bookings for their shops
        if request.user.role == 'client':
            return obj.shop.client.user == request.user
        
        # Staff can access their assigned bookings
        if request.user.role == 'staff':
            staff_profile = getattr(request.user, 'staff_profile', None)
            if staff_profile:
                return obj.staff_member_id == staff_profile.id
        
        return False
