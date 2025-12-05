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
    BulkScheduleCreateSerializer,
    BulkScheduleResponseSerializer,
    TimeSlotSerializer,
    TimeSlotGenerateSerializer,
    TimeSlotGenerateResponseSerializer,
    TimeSlotBlockSerializer,
    DynamicAvailabilityRequestSerializer,
    DynamicAvailabilityResponseSerializer,
    AvailableSlotSerializer
)
from .services.availability import AvailabilityService


class ShopScheduleViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    ViewSet for managing shop schedules.
    
    Use bulk_create to set shop hours for multiple days at once.
    Individual CRUD operations are not needed - bulk_create handles create/update.
    """
    queryset = ShopSchedule.objects.select_related('shop__client__user')
    serializer_class = ShopScheduleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Clients see only their schedules when authenticated
        if self.request.user.is_authenticated and self.request.user.role == 'client':
            queryset = queryset.filter(shop__client__user=self.request.user)
        
        return queryset
    
    @extend_schema(
        summary="List shop schedules",
        description="Get shop schedules. Filter by shop_id to get schedules for a specific shop.",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
        ],
        responses={200: ShopScheduleSerializer(many=True)},
        tags=['Schedules - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Set shop hours (bulk create/update)",
        description="""
        Set shop hours for multiple days at once.
        
        Example: Set Monday-Friday 9AM-6PM in one call.
        Existing schedules for those days will be updated automatically.
        """,
        request=BulkScheduleCreateSerializer,
        responses={
            200: BulkScheduleResponseSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Shop not found")
        },
        tags=['Schedules - Client']
    )
    @action(detail=False, methods=['post'], permission_classes=[IsClient])
    def bulk_create(self, request):
        """Create/update schedules for multiple days at once."""
        serializer = BulkScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        shop_id = serializer.validated_data['shop_id']
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']
        
        # Verify shop ownership
        from apps.shops.models import Shop
        try:
            shop = Shop.objects.get(id=shop_id, client__user=request.user)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found or you do not own this shop'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get days in range
        days = serializer.get_days_in_range()
        
        created_count = 0
        updated_count = 0
        
        for day in days:
            schedule, created = ShopSchedule.objects.update_or_create(
                shop=shop,
                day_of_week=day,
                defaults={
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return Response({
            'message': f'Successfully configured {len(days)} days',
            'schedules_created': created_count,
            'schedules_updated': updated_count,
            'days': days,
            'shop_hours': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
        })
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'list':
            return [AllowAny()]
        elif self.action == 'bulk_create':
            return [IsClient()]
        return super().get_permissions()


class TimeSlotViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    ViewSet for managing time slots.
    
    Main endpoints:
    - list: View manual slots (filtered by shop/date/status)
    - generate: Create manual slots for special requests
    - dynamic_availability: Get available slots dynamically (recommended)
    - block/unblock: Block manual slots
    """
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
        summary="List manual time slots",
        description="Get manually created time slots. Use dynamic_availability for available booking slots.",
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
        summary="Create manual time slot (Special Requests)",
        description="""
        Create a manual time slot for special requests only.
        
        Use this endpoint ONLY for:
        - VIP bookings with custom times
        - Special event reservations
        - Blocked times for maintenance/breaks
        
        For regular bookings, use /dynamic_availability/ + /dynamic_book/ instead.
        Manual slots are automatically considered in dynamic availability calculations.
        """,
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
        
        # Check for existing slots at the exact same time
        # Allow multiple slots for the same time period, limited by the number of active staff
        existing_slots_count = TimeSlot.objects.filter(
            schedule=schedule,
            start_datetime=current_time,
            end_datetime=end_time_dt
        ).count()
        
        # Get the number of active staff members for this shop
        from apps.staff.models import StaffMember
        active_staff_count = StaffMember.objects.filter(
            shop=shop,
            is_active=True
        ).count()
        
        # Prevent creating more slots than available staff members
        if existing_slots_count >= active_staff_count:
            return Response(
                {
                    'error': f'Cannot create more time slots. Maximum {active_staff_count} concurrent slots allowed (based on active staff count)',
                    'existing_slots': existing_slots_count,
                    'active_staff_count': active_staff_count,
                    'message': 'Add more staff members to create additional concurrent time slots',
                    'slots_created': 0,
                    'shop_details': {
                        'id': str(shop.id),
                        'name': shop.name,
                        'address': shop.address,
                        'city': shop.city
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle staff member assignment if provided
        staff_member = None
        staff_member_id = serializer.validated_data.get('staff_member_id')
        
        if staff_member_id:
            from apps.staff.models import StaffMember
            try:
                staff_member = StaffMember.objects.get(
                    id=staff_member_id,
                    shop=shop,
                    is_active=True
                )
            except StaffMember.DoesNotExist:
                return Response(
                    {'error': 'Staff member not found or not available at this shop'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        TimeSlot.objects.create(
            schedule=schedule,
            start_datetime=current_time,
            end_datetime=end_time_dt,
            staff_member=staff_member,
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
        summary="Dynamic availability calculator",
        description="""
        Calculate available time slots dynamically based on:
        - Shop schedule (open/close times for the day)
        - Service duration
        - Staff availability (booking conflicts)
        
        This endpoint computes slots on-the-fly without requiring pre-generated TimeSlot records.
        
        **Key Features:**
        - Handles staff concurrency (if Staff A is busy, Staff B may still be available)
        - Respects service duration (a 45-min service blocks appropriate time ranges)
        - Filters past slots with configurable buffer
        
        **Example Use Cases:**
        - Customer booking flow: Get available slots for a specific service on a date
        - Staff scheduling: See which time slots have no available staff
        """,
        request=DynamicAvailabilityRequestSerializer,
        responses={
            200: DynamicAvailabilityResponseSerializer,
            400: OpenApiResponse(description="Bad Request - Invalid service_id or date"),
            404: OpenApiResponse(description="Service not found")
        },
        tags=['Schedules - Public']
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def dynamic_availability(self, request):
        """
        Calculate available time slots dynamically.
        
        This replaces the need for pre-generated TimeSlot records by computing
        availability on-the-fly based on shop hours, service duration, and
        existing bookings.
        """
        serializer = DynamicAvailabilityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service_id = serializer.validated_data['service_id']
        target_date = serializer.validated_data['date']
        # Buffer is optional - if not provided, uses service.buffer_minutes
        buffer_minutes_override = serializer.validated_data.get('buffer_minutes_override')
        
        try:
            # Initialize the availability service
            # Slot interval automatically uses service duration
            availability_service = AvailabilityService(
                service_id=service_id,
                target_date=target_date,
                buffer_minutes=buffer_minutes_override
            )
            
            # Get available slots
            available_slots = availability_service.get_available_slots()
            
            # Get eligible staff count
            eligible_staff = availability_service._get_eligible_staff()
            
            # Build a map of staff details for quick lookup
            from apps.staff.models import StaffMember, StaffService
            staff_ids = set()
            for slot in available_slots:
                staff_ids.update(slot.available_staff_ids)
            
            staff_members = {
                str(s.id): s for s in StaffMember.objects.filter(id__in=staff_ids)
            }
            
            # Get primary staff for this service
            primary_staff_ids = set(
                StaffService.objects.filter(
                    service_id=service_id,
                    is_primary=True
                ).values_list('staff_member_id', flat=True)
            )
            
            # Build available slots with full staff details
            slots_data = []
            for slot in available_slots:
                staff_list = []
                for staff_id in slot.available_staff_ids:
                    staff = staff_members.get(str(staff_id))
                    if staff:
                        staff_list.append({
                            'id': staff_id,
                            'name': staff.name,
                            'email': staff.email,
                            'phone': staff.phone,
                            'profile_image': staff.profile_image.url if staff.profile_image else None,
                            'is_primary': staff_id in primary_staff_ids
                        })
                
                slots_data.append({
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'available_staff': staff_list,
                    'available_staff_count': len(staff_list)
                })
            
            # Build response
            response_data = {
                'shop_id': availability_service.shop.id,
                'shop_name': availability_service.shop.name,
                'service_id': availability_service.service.id,
                'service_name': availability_service.service.name,
                'service_duration_minutes': availability_service.service_duration,
                'date': target_date,
                'is_shop_open': availability_service.is_shop_open(),
                'shop_hours': availability_service.get_shop_hours(),
                'available_slots': slots_data,
                'total_available_slots': len(available_slots),
                'eligible_staff_count': eligible_staff.count()
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
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
        if self.action in ['list', 'dynamic_availability']:
            return [AllowAny()]
        elif self.action in ['block', 'unblock']:
            return [IsClient(), IsShopOwner()]
        elif self.action == 'generate':
            return [IsClient()]
        return super().get_permissions()
