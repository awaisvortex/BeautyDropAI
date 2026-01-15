"""
Client views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.db.models import Sum, Count

from apps.core.permissions import IsClient
from apps.core.messages import PROFILE
from .models import Client
from .serializers import (
    ClientSerializer,
    ClientCreateUpdateSerializer,
    ClientTotalEarningsSerializer
)


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Client model.
    
    Includes client profile management and earnings statistics.
    """
    queryset = Client.objects.all()
    permission_classes = [IsAuthenticated, IsClient]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ClientCreateUpdateSerializer
        elif self.action == 'total_earnings':
            return ClientTotalEarningsSerializer
        return ClientSerializer
    
    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Client.objects.none()
        
        # Clients can only see their own profile
        if self.request.user.is_authenticated and self.request.user.role == 'client':
            return Client.objects.filter(user=self.request.user)
        return Client.objects.none()
    
    @extend_schema(
        summary="Get my profile",
        description="Get the current client's (salon owner's) profile",
        responses={200: ClientSerializer},
        tags=['Clients']
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current client's profile"""
        try:
            client = request.user.client_profile
            return Response(ClientSerializer(client).data)
        except Client.DoesNotExist:
            return Response(
                PROFILE['client_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Total earnings across all shops",
        description="""
        Get the total earnings for the authenticated client (salon owner) across ALL their shops.
        
        Returns:
        - Grand total of earnings from completed bookings
        - Number of shops owned
        - Total completed bookings count
        - Breakdown of earnings per shop
        
        Earnings are calculated from the `total_price` of completed bookings.
        When a new shop is created, it will automatically be included in subsequent calls.
        """,
        responses={
            200: ClientTotalEarningsSerializer,
            404: OpenApiResponse(description="Client profile not found")
        },
        tags=['Clients']
    )
    @action(detail=False, methods=['get'], url_path='total-earnings')
    def total_earnings(self, request):
        """
        Get total earnings from all shops owned by the client.
        
        This aggregates completed booking revenue across all shops.
        """
        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response(
                {'error': 'Client profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.shops.models import Shop
        from apps.bookings.models import Booking
        from apps.payments.models import BookingPayment
        
        # Get all shops owned by this client
        shops = Shop.objects.filter(client=client)
        
        # Calculate earnings per shop
        shop_earnings = []
        grand_total = 0
        grand_total_advance_payments = 0
        total_completed_bookings = 0
        
        for shop in shops:
            bookings = Booking.objects.filter(shop=shop)
            total_bookings = bookings.count()
            completed = bookings.filter(status='completed')
            completed_count = completed.count()
            earnings = completed.aggregate(total=Sum('total_price'))['total'] or 0
            
            # Calculate advance payments for this shop
            advance_payments = BookingPayment.objects.filter(
                booking__shop=shop,
                status='paid'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            shop_earnings.append({
                'shop_id': shop.id,
                'shop_name': shop.name,
                'total_bookings': total_bookings,
                'completed_bookings': completed_count,
                'total_earnings': float(earnings),
                'total_advance_payments': float(advance_payments)
            })
            
            grand_total += earnings
            grand_total_advance_payments += advance_payments
            total_completed_bookings += completed_count
        
        return Response({
            'total_earnings': float(grand_total),
            'total_advance_payments': float(grand_total_advance_payments),
            'total_shops': shops.count(),
            'total_completed_bookings': total_completed_bookings,
            'shops': shop_earnings
        })
