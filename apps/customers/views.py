"""
Customer views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.core.permissions import IsCustomer
from apps.core.messages import PROFILE, SHOP as SHOP_MESSAGES
from apps.shops.serializers import ShopSerializer
from .models import Customer
from .serializers import CustomerSerializer, CustomerUpdateSerializer


class CustomerViewSet(viewsets.GenericViewSet):
    """
    ViewSet for Customer profile and favorites management.
    """
    queryset = Customer.objects.all()
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get_serializer_class(self):
        if self.action in ['update_profile', 'partial_update_profile']:
            return CustomerUpdateSerializer
        return CustomerSerializer
    
    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Customer.objects.none()
        
        # Customers can only see their own profile
        if self.request.user.is_authenticated and self.request.user.role == 'customer':
            return Customer.objects.filter(user=self.request.user)
        return Customer.objects.none()
    
    @extend_schema(
        summary="Get my profile",
        description="Get the current customer's profile",
        responses={200: CustomerSerializer},
        tags=['Customers']
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current customer's profile"""
        try:
            customer = request.user.customer_profile
            return Response(CustomerSerializer(customer).data)
        except Customer.DoesNotExist:
            return Response(
                PROFILE['customer_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Get favorite shops",
        description="Get list of all shops the customer has marked as favorite",
        responses={200: ShopSerializer(many=True)},
        tags=['Customers']
    )
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        """Get list of favorite shops"""
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response(
                PROFILE['customer_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        favorite_shops = customer.favorite_shops.filter(is_active=True)
        serializer = ShopSerializer(favorite_shops, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Add shop to favorites",
        description="Add a shop to the customer's favorites list",
        request=None,
        responses={
            200: {'description': 'Shop added to favorites'},
            400: OpenApiResponse(description="Shop already in favorites"),
            404: OpenApiResponse(description="Shop not found")
        },
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'message': 'Shop added to favorites',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Salon',
                    'favorites_count': 5
                },
                response_only=True
            )
        ],
        tags=['Customers']
    )
    @action(detail=False, methods=['post'], url_path='favorites/(?P<shop_id>[^/.]+)/add')
    def add_favorite(self, request, shop_id=None):
        """Add a shop to favorites"""
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response(
                PROFILE['customer_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, is_active=True)
        except Shop.DoesNotExist:
            return Response(
                SHOP_MESSAGES['not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        if customer.favorite_shops.filter(id=shop_id).exists():
            return Response(
                SHOP_MESSAGES['already_favorite'],
                status=status.HTTP_400_BAD_REQUEST
            )
        
        customer.favorite_shops.add(shop)
        
        return Response({
            'message': 'Shop added to favorites',
            'shop_id': str(shop.id),
            'shop_name': shop.name,
            'favorites_count': customer.favorite_shops.count()
        })
    
    @extend_schema(
        summary="Remove shop from favorites",
        description="Remove a shop from the customer's favorites list",
        request=None,
        responses={
            200: {'description': 'Shop removed from favorites'},
            400: OpenApiResponse(description="Shop not in favorites"),
            404: OpenApiResponse(description="Shop not found")
        },
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    'message': 'Shop removed from favorites',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'favorites_count': 4
                },
                response_only=True
            )
        ],
        tags=['Customers']
    )
    @action(detail=False, methods=['post'], url_path='favorites/(?P<shop_id>[^/.]+)/remove')
    def remove_favorite(self, request, shop_id=None):
        """Remove a shop from favorites"""
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response(
                PROFILE['customer_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                SHOP_MESSAGES['not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not customer.favorite_shops.filter(id=shop_id).exists():
            return Response(
                SHOP_MESSAGES['not_in_favorites'],
                status=status.HTTP_400_BAD_REQUEST
            )
        
        customer.favorite_shops.remove(shop)
        
        return Response({
            'message': 'Shop removed from favorites',
            'shop_id': str(shop.id),
            'favorites_count': customer.favorite_shops.count()
        })
    
    @extend_schema(
        summary="Toggle shop favorite",
        description="Toggle a shop's favorite status. Adds if not in favorites, removes if already favorited.",
        request=None,
        responses={
            200: {'description': 'Favorite status toggled'},
            404: OpenApiResponse(description="Shop not found")
        },
        examples=[
            OpenApiExample(
                'Added to favorites',
                value={
                    'message': 'Shop added to favorites',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Salon',
                    'is_favorite': True,
                    'favorites_count': 5
                },
                response_only=True
            ),
            OpenApiExample(
                'Removed from favorites',
                value={
                    'message': 'Shop removed from favorites',
                    'shop_id': 'e188f3d1-921d-4261-9ea5-d6cfad62962a',
                    'shop_name': 'Elegant Salon',
                    'is_favorite': False,
                    'favorites_count': 4
                },
                response_only=True
            )
        ],
        tags=['Customers']
    )
    @action(detail=False, methods=['post'], url_path='favorites/(?P<shop_id>[^/.]+)/toggle')
    def toggle_favorite(self, request, shop_id=None):
        """Toggle a shop's favorite status"""
        try:
            customer = request.user.customer_profile
        except Customer.DoesNotExist:
            return Response(
                PROFILE['customer_not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, is_active=True)
        except Shop.DoesNotExist:
            return Response(
                SHOP_MESSAGES['not_found'],
                status=status.HTTP_404_NOT_FOUND
            )
        
        if customer.favorite_shops.filter(id=shop_id).exists():
            customer.favorite_shops.remove(shop)
            is_favorite = False
            message = 'Shop removed from favorites'
        else:
            customer.favorite_shops.add(shop)
            is_favorite = True
            message = 'Shop added to favorites'
        
        return Response({
            'message': message,
            'shop_id': str(shop.id),
            'shop_name': shop.name,
            'is_favorite': is_favorite,
            'favorites_count': customer.favorite_shops.count()
        })
