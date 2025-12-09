"""
Staff Dashboard views - endpoints for staff members to access their own data
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.permissions import IsStaff
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingListSerializer
from apps.services.serializers import ServiceSerializer
from .models import StaffMember
from .serializers import StaffMemberDetailSerializer


class StaffDashboardViewSet(viewsets.GenericViewSet):
    """
    Staff member's own dashboard endpoints.
    All endpoints require staff authentication.
    """
    permission_classes = [IsAuthenticated, IsStaff]
    
    def get_staff_profile(self, request):
        """Get the current user's staff profile"""
        staff_profile = getattr(request.user, 'staff_profile', None)
        if not staff_profile:
            return None
        return staff_profile
    
    @extend_schema(
        summary="Get my profile",
        description="Get the current staff member's profile including shop info and assigned services",
        responses={
            200: StaffMemberDetailSerializer,
            404: OpenApiResponse(description="Staff profile not found")
        },
        tags=['Staff Dashboard']
    )
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """Get current staff member's profile"""
        staff = self.get_staff_profile(request)
        if not staff:
            return Response(
                {'error': 'Staff profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(StaffMemberDetailSerializer(staff).data)
    
    @extend_schema(
        summary="Get my services",
        description="Get all services assigned to the current staff member",
        responses={200: ServiceSerializer(many=True)},
        tags=['Staff Dashboard']
    )
    @action(detail=False, methods=['get'], url_path='my-services')
    def my_services(self, request):
        """Get services assigned to current staff member"""
        staff = self.get_staff_profile(request)
        if not staff:
            return Response(
                {'error': 'Staff profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        services = staff.services.all()
        return Response(ServiceSerializer(services, many=True).data)
    
    @extend_schema(
        summary="Get my bookings",
        description="Get all bookings assigned to the current staff member. Optionally filter by status.",
        responses={200: BookingListSerializer(many=True)},
        tags=['Staff Dashboard']
    )
    @action(detail=False, methods=['get'], url_path='my-bookings')
    def my_bookings(self, request):
        """Get current staff's bookings"""
        staff = self.get_staff_profile(request)
        if not staff:
            return Response(
                {'error': 'Staff profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        bookings = Booking.objects.filter(
            staff_member=staff
        ).select_related('customer__user', 'service', 'shop').order_by('-booking_datetime')
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        return Response(BookingListSerializer(bookings, many=True).data)
    
    @extend_schema(
        summary="Get upcoming bookings",
        description="Get upcoming confirmed/pending bookings for the current staff member",
        responses={200: BookingListSerializer(many=True)},
        tags=['Staff Dashboard']
    )
    @action(detail=False, methods=['get'], url_path='upcoming-bookings')
    def upcoming_bookings(self, request):
        """Get upcoming bookings for current staff"""
        from django.utils import timezone
        
        staff = self.get_staff_profile(request)
        if not staff:
            return Response(
                {'error': 'Staff profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        now = timezone.now()
        bookings = Booking.objects.filter(
            staff_member=staff,
            booking_datetime__gte=now,
            status__in=['pending', 'confirmed']
        ).select_related('customer__user', 'service', 'shop').order_by('booking_datetime')
        
        return Response(BookingListSerializer(bookings, many=True).data)
    
    @extend_schema(
        summary="Get today's bookings",
        description="Get all bookings for today assigned to the current staff member",
        responses={200: BookingListSerializer(many=True)},
        tags=['Staff Dashboard']
    )
    @action(detail=False, methods=['get'], url_path='today-bookings')
    def today_bookings(self, request):
        """Get today's bookings for current staff"""
        from django.utils import timezone
        
        staff = self.get_staff_profile(request)
        if not staff:
            return Response(
                {'error': 'Staff profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        today = timezone.now().date()
        bookings = Booking.objects.filter(
            staff_member=staff,
            booking_datetime__date=today
        ).select_related('customer__user', 'service', 'shop').order_by('booking_datetime')
        
        return Response(BookingListSerializer(bookings, many=True).data)
