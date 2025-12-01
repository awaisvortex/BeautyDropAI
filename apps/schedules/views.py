"""
Schedule and TimeSlot views
"""
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes
from django.utils import timezone
from datetime import datetime, timedelta

from apps.core.permissions import IsClient, IsShopOwner
from .models import ShopSchedule, TimeSlot
from .serializers import (
    ShopScheduleSerializer,
    ShopScheduleCreateUpdateSerializer,
    TimeSlotSerializer,
    TimeSlotGenerateSerializer,
    TimeSlotGenerateResponseSerializer,
    AvailabilityCheckSerializer,
    AvailabilityResponseSerializer,
    TimeSlotBlockSerializer
)


class ShopScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing shop schedules"""
    queryset = ShopSchedule.objects.select_related('shop__client__user')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ShopScheduleCreateUpdateSerializer
        return ShopScheduleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Clients see only their schedules
        if self.request.user.role == 'client':
            queryset = queryset.filter(shop__client__user=self.request.user)
        
        return queryset
    
    @extend_schema(
        summary="List shop schedules",
        description="Get shop schedules. Filter by shop_id to get schedules for a specific shop.",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
        ],
        responses={200: ShopScheduleSerializer(many=True)},
        tags=['Schedules - Client']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create shop schedule",
        description="Create a new schedule for a shop (salon owners only). Requires shop_id in request body.",
        request=ShopScheduleCreateUpdateSerializer,
        responses={
            201: ShopScheduleSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden")
        },
        tags=['Schedules - Client']
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != 'client':
            return Response(
                {'error': 'Only salon owners can create schedules'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get shop from request data
        shop_id = request.data.get('shop_id')
        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify shop ownership
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, client__user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found or you do not own this shop'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        
        # Check if schedule already exists for this day
        existing_schedule = ShopSchedule.objects.filter(
            shop=shop,
            day_of_week=serializer.validated_data['day_of_week']
        ).first()
        
        if existing_schedule:
            return Response(
                {
                    'error': f'A schedule for {serializer.validated_data["day_of_week"]} already exists for this shop',
                    'existing_schedule_id': str(existing_schedule.id),
                    'message': 'Use PUT or PATCH to update the existing schedule'
                },
                status=status.HTTP_409_CONFLICT
            )
        
        schedule = serializer.save(shop=shop)
        return Response(
            ShopScheduleSerializer(schedule).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Get schedule details",
        description="Retrieve detailed information about a specific schedule",
        responses={
            200: ShopScheduleSerializer,
            404: OpenApiResponse(description="Schedule not found")
        },
        tags=['Schedules - Client']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Update shop schedule",
        description="Update schedule details (salon owners only)",
        request=ShopScheduleCreateUpdateSerializer,
        responses={
            200: ShopScheduleSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Schedule not found")
        },
        tags=['Schedules - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update shop schedule",
        description="Partially update schedule details (salon owners only)",
        request=ShopScheduleCreateUpdateSerializer,
        responses={
            200: ShopScheduleSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Schedule not found")
        },
        tags=['Schedules - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete shop schedule",
        description="Delete a schedule (salon owners only)",
        responses={
            204: OpenApiResponse(description="Schedule deleted successfully"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Schedule not found")
        },
        tags=['Schedules - Client']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsClient(), IsShopOwner()]
        return super().get_permissions()


class TimeSlotViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing time slots"""
    queryset = TimeSlot.objects.select_related('schedule__shop')
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(schedule__shop_id=shop_id)
        
        # Filter by date if provided
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(start_datetime__date=date)
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('start_datetime')
    
    @extend_schema(
        summary="List time slots",
        description="Get time slots with optional filters",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
            OpenApiParameter('date', str, description='Filter by date (YYYY-MM-DD)'),
            OpenApiParameter('status', str, description='Filter by status (available, booked, blocked)'),
        ],
        responses={200: TimeSlotSerializer(many=True)},
        tags=['Schedules - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get time slot details",
        description="Retrieve detailed information about a specific time slot",
        responses={
            200: TimeSlotSerializer,
            404: OpenApiResponse(description="Time slot not found")
        },
        tags=['Schedules - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Update time slot",
        description="Update time slot details (salon owners only)",
        request=TimeSlotSerializer,
        responses={
            200: TimeSlotSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Time slot not found")
        },
        tags=['Schedules - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update time slot",
        description="Partially update time slot details (salon owners only)",
        request=TimeSlotSerializer,
        responses={
            200: TimeSlotSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Time slot not found")
        },
        tags=['Schedules - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Generate time slots",
        description="Generate time slots for a shop based on its schedules (salon owners only)",
        request=TimeSlotGenerateSerializer,
        responses={
            200: TimeSlotGenerateResponseSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Schedules - Client']
    )
    @action(detail=False, methods=['post', 'patch'], permission_classes=[IsClient])
    def generate(self, request):
        """Generate time slots for a date range"""
        serializer = TimeSlotGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        shop_id = serializer.validated_data['shop_id']
        start_date = serializer.validated_data['start_date']
        day_name = serializer.validated_data['day_name']
        start_time_req = serializer.validated_data['start_time']
        end_time_req = serializer.validated_data['end_time']
        
        # Verify shop ownership
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, client__user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found or you do not own this shop'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculate target date
        # Find the next occurrence of day_name on or after start_date
        days_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        target_day_num = days_map[day_name.lower()]
        current_day_num = start_date.weekday()
        
        days_ahead = target_day_num - current_day_num
        if days_ahead < 0:
            days_ahead += 7
        target_date = start_date + timedelta(days=days_ahead)
        
        # Find or create schedule for this day
        # Auto-create a default schedule if one doesn't exist to allow flexible slot creation
        schedule, created = ShopSchedule.objects.get_or_create(
            shop=shop,
            day_of_week=day_name.lower(),
            defaults={
                'start_time': start_time_req,
                'end_time': end_time_req,
                'is_active': True,
                'slot_duration_minutes': 30  # Default duration
            }
        )
        
        if created:
            print(f"DEBUG: Auto-created schedule for {day_name}")
            
        # Create the slot
        current_time = datetime.combine(target_date, start_time_req)
        end_time_dt = datetime.combine(target_date, end_time_req)
        
        # Check for existing slots that overlap
        # We want to prevent exact duplicates or overlaps for the same shop/schedule
        overlapping_slots = TimeSlot.objects.filter(
            schedule=schedule,
            start_datetime__lt=end_time_dt,
            end_datetime__gt=current_time
        )
        
        if overlapping_slots.exists():
            return Response(
                {
                    'message': 'Slot already exists or overlaps with an existing slot',
                    'slots_created': 0,
                    'shop_details': {
                        'id': str(shop.id),
                        'name': shop.name,
                        'address': shop.address,
                        'city': shop.city
                    }
                },
                status=status.HTTP_200_OK
            )

        TimeSlot.objects.create(
            schedule=schedule,
            start_datetime=current_time,
            end_datetime=end_time_dt,
            status='available'
        )
        
        # Calculate duration in minutes
        duration_minutes = int((end_time_dt - current_time).total_seconds() / 60)
        
        response_data = {
            'message': 'Successfully created 1 time slot',
            'slots_created': 1,
            'date': target_date.isoformat(),
            'duration_minutes': duration_minutes,
            'shop_details': {
                'id': str(shop.id),
                'name': shop.name,
                'address': shop.address,
                'city': shop.city
            }
        }
        
        return Response(response_data)
    
    @extend_schema(
        summary="Check availability",
        description="Check available time slots for a shop on a specific date",
        request=AvailabilityCheckSerializer,
        responses={200: AvailabilityResponseSerializer},
        tags=['Schedules - Public']
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def check_availability(self, request):
        """Check available time slots"""
        serializer = AvailabilityCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        shop_id = serializer.validated_data['shop_id']
        date = serializer.validated_data['date']
        service_id = serializer.validated_data.get('service_id')
        
        # Get available slots
        slots = TimeSlot.objects.filter(
            schedule__shop_id=shop_id,
            start_datetime__date=date,
            start_datetime__gte=timezone.now(),
            status='available'
        ).order_by('start_datetime')
        
        response_data = {
            'date': date,
            'available_slots': TimeSlotSerializer(slots, many=True).data,
            'total_slots': slots.count()
        }
        
        return Response(response_data)
    
    @extend_schema(
        summary="Block time slot",
        description="Block a time slot (salon owners only)",
        request=TimeSlotBlockSerializer,
        responses={
            200: TimeSlotSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Time slot not found")
        },
        tags=['Schedules - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def block(self, request, pk=None):
        """Block a time slot"""
        time_slot = self.get_object()
        
        if time_slot.status == 'booked':
            return Response(
                {'error': 'Cannot block a booked time slot'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        time_slot.status = 'blocked'
        time_slot.save(update_fields=['status'])
        
        return Response(TimeSlotSerializer(time_slot).data)
    
    @extend_schema(
        summary="Unblock time slot",
        description="Unblock a time slot (salon owners only)",
        request=None,
        responses={
            200: TimeSlotSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Time slot not found")
        },
        tags=['Schedules - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def unblock(self, request, pk=None):
        """Unblock a time slot"""
        time_slot = self.get_object()
        time_slot.status = 'available'
        time_slot.save(update_fields=['status'])
        
        return Response(TimeSlotSerializer(time_slot).data)

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['update', 'partial_update', 'block', 'unblock']:
            return [IsClient(), IsShopOwner()]
        elif self.action == 'generate':
            return [IsClient()]
        return super().get_permissions()
