"""
Staff views
"""
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.core.permissions import IsClient, IsShopOwner
from .models import StaffMember, StaffService
from .serializers import (
    StaffMemberSerializer,
    StaffMemberCreateUpdateSerializer,
    StaffMemberDetailSerializer,
    StaffServiceAssignmentSerializer,
    ResendVerificationLinkSerializer,
    StaffDeleteErrorSerializer
)
from apps.core.serializers import SuccessResponseSerializer


class StaffMemberViewSet(viewsets.ModelViewSet):
    """ViewSet for managing staff members"""
    queryset = StaffMember.objects.select_related('shop').prefetch_related('staff_services__service')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'is_active']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StaffMemberDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return StaffMemberCreateUpdateSerializer
        return StaffMemberSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by shop if provided
        shop_id = self.request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Handle unauthenticated users (public access for viewing)
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_active=True)
        # Clients see only their shop's staff
        elif self.request.user.is_authenticated and self.request.user.role == 'client':
            if self.action not in ['list', 'retrieve', 'available_for_service']:
                queryset = queryset.filter(shop__client__user=self.request.user)
        # Customers see only active staff
        elif self.request.user.is_authenticated and self.request.user.role == 'customer':
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @extend_schema(
        summary="List staff members",
        description="Get all staff members. Filter by shop_id to get staff for a specific shop. Public endpoint.",
        parameters=[
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Filter by shop ID'),
            OpenApiParameter('is_active', bool, description='Filter by active status'),
            OpenApiParameter('search', str, description='Search in name, email, phone'),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get staff member details",
        description="Retrieve detailed information about a specific staff member including assigned services. Public endpoint.",
        responses={
            200: StaffMemberDetailSerializer,
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Public']
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get staff member details with auto-sync.
        
        If staff has invite_status='sent' but no linked user, 
        check if a user with matching email exists to auto-link.
        """
        instance = self.get_object()
        
        # Auto-sync: Check if staff accepted invitation but webhook was missed
        if instance.invite_status == 'sent' and instance.user is None and instance.email:
            from apps.authentication.models import User
            from django.utils import timezone
            
            try:
                # Check if user with matching email exists
                user = User.objects.get(email__iexact=instance.email)
                
                # Link user to staff member
                instance.user = user
                instance.invite_status = 'accepted'
                instance.invite_accepted_at = timezone.now()
                instance.save(update_fields=['user', 'invite_status', 'invite_accepted_at'])
                
                # Ensure user has staff role
                if user.role != 'staff':
                    user.role = 'staff'
                    user.save(update_fields=['role'])
                    
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Auto-synced staff {instance.name} ({instance.email}) - linked to user")
                
            except User.DoesNotExist:
                pass  # User hasn't signed up yet, that's fine
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error auto-syncing staff {instance.email}: {e}")
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create staff member",
        description="Add a new staff member to a shop and send invitation email (salon owners only). Requires shop_id and email in request body.",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            201: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden - Only salon owners can create staff")
        },
        tags=['Staff - Client']
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != 'client':
            return Response(
                {'error': 'Only salon owners can create staff members'},
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
        
        staff_member = serializer.save(shop=shop)
        
        # Send Clerk invitation if requested
        send_invite = serializer.validated_data.get('send_invite', True)
        if send_invite and staff_member.email:
            from apps.authentication.services.clerk_api import clerk_client
            from django.conf import settings
            from django.utils import timezone
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Build redirect URL for staff portal
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            redirect_url = f"{frontend_url}/staff/complete-signup"
            
            invitation = clerk_client.create_invitation(
                email_address=staff_member.email,
                redirect_url=redirect_url,
                public_metadata={
                    'role': 'staff',
                    'shop_id': str(shop.id),
                    'staff_member_id': str(staff_member.id)
                }
            )
            
            if invitation:
                staff_member.invite_status = 'sent'
                staff_member.invite_sent_at = timezone.now()
                staff_member.clerk_invitation_id = invitation.get('id', '')
                staff_member.save(update_fields=['invite_status', 'invite_sent_at', 'clerk_invitation_id'])
                logger.info(f"Invitation sent to staff member {staff_member.email}")
            else:
                logger.error(f"Failed to send invitation to staff member {staff_member.email}")
        
        return Response(
            StaffMemberSerializer(staff_member).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Update staff member",
        description="Update staff member details (salon owners only)",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            200: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update staff member",
        description="Partially update staff member details (salon owners only)",
        request=StaffMemberCreateUpdateSerializer,
        responses={
            200: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete staff member",
        description="""
        Remove a staff member from a shop (salon owners only).
        
        **Restrictions:**
        - Cannot delete if staff has pending or confirmed bookings
        - Reassign all active bookings to other staff first using `/bookings/{id}/reassign_staff/`
        - Then the staff member can be deleted
        """,
        responses={
            200: SuccessResponseSerializer,
            400: StaffDeleteErrorSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    def destroy(self, request, *args, **kwargs):
        staff_member = self.get_object()
        staff_name = staff_member.name
        
        # Check for active bookings assigned to this staff
        from apps.bookings.models import Booking
        active_bookings = Booking.objects.filter(
            staff_member=staff_member,
            status__in=['pending', 'confirmed']
        ).order_by('booking_datetime')
        
        active_count = active_bookings.count()
        if active_count > 0:
            # Get booking details for error message
            booking_details = []
            for booking in active_bookings[:5]:  # Show first 5
                booking_details.append({
                    'id': str(booking.id),
                    'datetime': booking.booking_datetime.isoformat(),
                    'service': booking.service.name,
                    'customer': booking.customer.user.full_name if booking.customer else 'Unknown'
                })
            
            return Response(
                {
                    'error': 'Cannot delete staff member with active bookings',
                    'active_bookings_count': active_count,
                    'message': f"{staff_name} has {active_count} pending/confirmed booking(s). Reassign them to other staff first using /api/v1/bookings/{{id}}/reassign_staff/",
                    'action_required': 'Use POST /api/v1/bookings/{booking_id}/reassign_staff/ to reassign each booking',
                    'bookings_to_reassign': booking_details,
                    'showing_first': min(5, active_count)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(staff_member)
        return Response(
            {"success": True, "message": f"Staff member '{staff_name}' deleted successfully"},
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Toggle staff availability",
        description="Mark staff as available or unavailable (e.g., for sick days, days off). Salon owners only.",
        request=None,
        responses={
            200: StaffMemberSerializer,
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsClient, IsShopOwner])
    def toggle_availability(self, request, pk=None):
        """Toggle staff availability status"""
        staff_member = self.get_object()
        staff_member.is_active = not staff_member.is_active
        staff_member.save(update_fields=['is_active'])
        
        return Response(
            StaffMemberSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Assign services to staff",
        description="Assign one or more services to a staff member. Can mark staff as primary for specific services (salon owners only).",
        request=StaffServiceAssignmentSerializer,
        responses={
            200: StaffMemberDetailSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member or service not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def assign_services(self, request, pk=None):
        """Assign services to a staff member"""
        staff_member = self.get_object()
        serializer = StaffServiceAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service_ids = serializer.validated_data['service_ids']
        is_primary = serializer.validated_data.get('is_primary', False)
        
        # Verify all services belong to the same shop
        from apps.services.models import Service
        services = Service.objects.filter(id__in=service_ids, shop=staff_member.shop)
        
        if services.count() != len(service_ids):
            return Response(
                {'error': 'One or more services not found or do not belong to this shop'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Assign services
        for service in services:
            StaffService.objects.update_or_create(
                staff_member=staff_member,
                service=service,
                defaults={'is_primary': is_primary}
            )
        
        return Response(
            StaffMemberDetailSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Remove service from staff",
        description="Remove a service assignment from a staff member (salon owners only)",
        parameters=[
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Service ID to remove', required=True),
        ],
        responses={
            200: StaffMemberDetailSerializer,
            400: OpenApiResponse(description="Bad Request"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member or service not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['delete'], permission_classes=[IsClient, IsShopOwner])
    def remove_service(self, request, pk=None):
        """Remove a service from a staff member"""
        staff_member = self.get_object()
        service_id = request.query_params.get('service_id')
        
        if not service_id:
            return Response(
                {'error': 'service_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            staff_service = StaffService.objects.get(
                staff_member=staff_member,
                service_id=service_id
            )
            staff_service.delete()
        except StaffService.DoesNotExist:
            return Response(
                {'error': 'Service assignment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(
            StaffMemberDetailSerializer(staff_member).data,
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Get available staff for time slot",
        description="Get all staff members available for a specific time slot (not already booked). Optionally filter by service. Public endpoint for customer booking.",
        parameters=[
            OpenApiParameter('time_slot_id', OpenApiTypes.UUID, description='Time Slot ID', required=True),
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Optional: Filter by service ID'),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def available_for_time_slot(self, request):
        """Get staff members available for a specific time slot"""
        from apps.schedules.models import TimeSlot
        from apps.bookings.models import Booking
        
        time_slot_id = request.query_params.get('time_slot_id')
        service_id = request.query_params.get('service_id')
        
        if not time_slot_id:
            return Response(
                {'error': 'time_slot_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            time_slot = TimeSlot.objects.get(id=time_slot_id)
        except TimeSlot.DoesNotExist:
            return Response(
                {'error': 'Time slot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all active staff for this shop
        all_staff = StaffMember.objects.filter(
            shop=time_slot.schedule.shop,
            is_active=True
        )
        
        # Filter by service if provided
        if service_id:
            # Include staff with no service assignments (free staff) OR staff assigned to this service
            all_staff = all_staff.filter(
                models.Q(services__id=service_id) | models.Q(services__isnull=True)
            ).distinct()
        
        # Exclude staff who are already booked for this time slot
        available_staff_ids = []
        for staff in all_staff:
            conflicting_booking = Booking.objects.filter(
                staff_member=staff,
                time_slot__start_datetime__lt=time_slot.end_datetime,
                time_slot__end_datetime__gt=time_slot.start_datetime,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if not conflicting_booking:
                available_staff_ids.append(staff.id)
        
        available_staff = StaffMember.objects.filter(id__in=available_staff_ids)
        serializer = StaffMemberSerializer(available_staff, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get available staff for service",
        description="Get all staff members who can provide a specific service. Public endpoint for customer booking.",
        parameters=[
            OpenApiParameter('service_id', OpenApiTypes.UUID, description='Service ID', required=True),
            OpenApiParameter('shop_id', OpenApiTypes.UUID, description='Shop ID', required=True),
        ],
        responses={200: StaffMemberSerializer(many=True)},
        tags=['Staff - Public']
    )
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def available_for_service(self, request):
        """Get staff members available for a specific service"""
        service_id = request.query_params.get('service_id')
        shop_id = request.query_params.get('shop_id')
        
        if not service_id or not shop_id:
            return Response(
                {'error': 'Both service_id and shop_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get staff members who can provide this service (including free staff)
        from django.db import models
        staff_members = StaffMember.objects.filter(
            shop_id=shop_id,
            is_active=True
        ).filter(
            models.Q(services__id=service_id) | models.Q(services__isnull=True)
        ).distinct()
        
        serializer = StaffMemberSerializer(staff_members, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Resend invitation",
        description="Resend invitation email to a staff member who hasn't accepted yet (salon owners only)",
        responses={
            200: StaffMemberSerializer,
            400: OpenApiResponse(description="Bad Request - Staff already has an account"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Staff member not found")
        },
        tags=['Staff - Client']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def resend_invite(self, request, pk=None):
        """Resend invitation email to staff member"""
        staff_member = self.get_object()
        
        if staff_member.user is not None:
            return Response(
                {'error': 'Staff member already has an account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if staff_member.invite_status == 'accepted':
            return Response(
                {'error': 'Invitation already accepted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.authentication.services.clerk_api import clerk_client
        from django.conf import settings
        from django.utils import timezone
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Revoke old invitation if exists
        if staff_member.clerk_invitation_id:
            clerk_client.revoke_invitation(staff_member.clerk_invitation_id)
        
        # Send new invitation
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        redirect_url = f"{frontend_url}/staff/complete-signup"
        
        invitation = clerk_client.create_invitation(
            email_address=staff_member.email,
            redirect_url=redirect_url,
            public_metadata={
                'role': 'staff',
                'shop_id': str(staff_member.shop.id),
                'staff_member_id': str(staff_member.id)
            }
        )
        
        if invitation and 'error' not in invitation:
            staff_member.invite_status = 'sent'
            staff_member.invite_sent_at = timezone.now()
            staff_member.clerk_invitation_id = invitation.get('id', '')
            staff_member.save(update_fields=['invite_status', 'invite_sent_at', 'clerk_invitation_id'])
            logger.info(f"Invitation resent to staff member {staff_member.email}")
            
            return Response(StaffMemberSerializer(staff_member).data)
        else:
            error_message = 'Failed to send invitation'
            if invitation and 'error' in invitation:
                error_message = invitation['error']
            return Response(
                {'error': error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Resend verification link",
        description="""
        Resend Clerk verification/invitation link to a staff member.
        
        Use this endpoint when:
        - The first invitation email wasn't received
        - The invitation link has expired
        - Staff member needs a new link for any reason
        
        Requires staff_id and email for verification.
        """,
        request=ResendVerificationLinkSerializer,
        responses={
            200: OpenApiResponse(
                description="Verification link sent successfully",
                response={
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string', 'example': 'Verification link sent successfully to jane@example.com'},
                        'staff_member': {'type': 'object'}
                    }
                }
            ),
            400: OpenApiResponse(description="Bad Request - Invalid data or staff already has account"),
            403: OpenApiResponse(description="Forbidden - Not shop owner"),
            404: OpenApiResponse(description="Staff member not found or email mismatch")
        },
        tags=['Staff - Client']
    )
    @action(detail=False, methods=['post'], permission_classes=[IsClient, IsShopOwner])
    def resend_verification_link(self, request):
        """
        Resend verification/invitation link to staff member.
        
        Takes staff_id and email in request body for verification.
        Salon owners can use this to resend links if original expired or wasn't received.
        """
        staff_id = request.data.get('staff_id')
        email = request.data.get('email')
        
        # Validate required fields
        if not staff_id or not email:
            return Response(
                {'error': 'Both staff_id and email are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find staff member
        try:
            staff_member = StaffMember.objects.select_related('shop').get(id=staff_id)
        except (StaffMember.DoesNotExist, ValueError):
            return Response(
                {'error': 'Staff member not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify email matches
        if staff_member.email.lower() != email.lower():
            return Response(
                {'error': 'Email does not match staff member record'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify shop ownership
        if staff_member.shop.client.user != request.user:
            return Response(
                {'error': 'You are not the owner of this shop'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already has account
        if staff_member.user is not None:
            return Response(
                {'error': 'Staff member already has an account. They can use forgot password if needed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if staff_member.invite_status == 'accepted':
            return Response(
                {'error': 'Invitation already accepted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.authentication.services.clerk_api import clerk_client
        from django.conf import settings
        from django.utils import timezone
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Revoke old invitation if exists
        if staff_member.clerk_invitation_id:
            try:
                clerk_client.revoke_invitation(staff_member.clerk_invitation_id)
            except Exception as e:
                logger.warning(f"Could not revoke old invitation: {e}")
        
        # Send new invitation
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        redirect_url = f"{frontend_url}/staff/complete-signup"
        
        invitation = clerk_client.create_invitation(
            email_address=staff_member.email,
            redirect_url=redirect_url,
            public_metadata={
                'role': 'staff',
                'shop_id': str(staff_member.shop.id),
                'staff_member_id': str(staff_member.id)
            }
        )
        
        if invitation and 'error' not in invitation:
            staff_member.invite_status = 'sent'
            staff_member.invite_sent_at = timezone.now()
            staff_member.clerk_invitation_id = invitation.get('id', '')
            staff_member.save(update_fields=['invite_status', 'invite_sent_at', 'clerk_invitation_id'])
            logger.info(f"Verification link resent to staff member {staff_member.email}")
            
            return Response({
                'message': f'Verification link sent successfully to {staff_member.email}',
                'staff_member': StaffMemberSerializer(staff_member).data
            })
        else:
            error_message = 'Failed to send verification link. Please try again later.'
            if invitation and 'error' in invitation:
                error_message = invitation['error']
            return Response(
                {'error': error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'available_for_service', 'available_for_time_slot']:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_availability', 'assign_services', 'remove_service', 'resend_invite', 'resend_verification_link']:
            return [IsClient(), IsShopOwner()]
        return super().get_permissions()
    
    @extend_schema(
        summary="Sync staff with Clerk",
        description="""
        Synchronize staff member status with Clerk users.
        
        This endpoint checks Clerk for users with matching emails and updates
        the invite_status and invite_accepted_at for staff members who have 
        completed signup but weren't properly tracked.
        
        Use this to fix staff members who show as 'sent' but have actually
        accepted their invitation.
        """,
        responses={
            200: OpenApiResponse(
                description="Sync completed",
                response={
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'},
                        'synced_count': {'type': 'integer'},
                        'synced_staff': {'type': 'array'}
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden")
        },
        tags=['Staff - Client']
    )
    @action(detail=False, methods=['post'], permission_classes=[IsClient])
    def sync_with_clerk(self, request):
        """
        Sync staff members with Clerk to fix any status mismatches.
        Matches staff by email and updates invite status if user exists in Clerk.
        """
        from apps.authentication.services.clerk_api import clerk_client
        from apps.authentication.models import User
        from django.utils import timezone
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get client's shops
        try:
            client = request.user.client_profile
            shop_ids = client.shops.values_list('id', flat=True)
        except Exception:
            return Response(
                {'error': 'Client profile not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get staff members with pending invites for this client's shops
        pending_staff = StaffMember.objects.filter(
            shop_id__in=shop_ids,
            invite_status='sent',
            user__isnull=True
        )
        
        synced = []
        
        for staff in pending_staff:
            # Check if user with this email exists in Django
            try:
                user = User.objects.get(email__iexact=staff.email)
                
                # Link user to staff member
                staff.user = user
                staff.invite_status = 'accepted'
                staff.invite_accepted_at = timezone.now()
                staff.save(update_fields=['user', 'invite_status', 'invite_accepted_at'])
                
                # Update user role if needed
                if user.role != 'staff':
                    user.role = 'staff'
                    user.save(update_fields=['role'])
                
                synced.append({
                    'staff_id': str(staff.id),
                    'email': staff.email,
                    'name': staff.name
                })
                logger.info(f"Synced staff {staff.name} ({staff.email})")
                
            except User.DoesNotExist:
                # User not in Django yet, try Clerk API
                clerk_user = clerk_client.get_user_by_email(staff.email)
                if clerk_user:
                    # Create user in Django and link
                    user = User.objects.create(
                        clerk_user_id=clerk_user['id'],
                        email=staff.email,
                        first_name=clerk_user.get('first_name', ''),
                        last_name=clerk_user.get('last_name', ''),
                        role='staff',
                        email_verified=True,
                        is_active=True
                    )
                    
                    staff.user = user
                    staff.invite_status = 'accepted'
                    staff.invite_accepted_at = timezone.now()
                    staff.save(update_fields=['user', 'invite_status', 'invite_accepted_at'])
                    
                    synced.append({
                        'staff_id': str(staff.id),
                        'email': staff.email,
                        'name': staff.name
                    })
                    logger.info(f"Synced staff {staff.name} ({staff.email}) from Clerk")
            
            except Exception as e:
                logger.error(f"Error syncing staff {staff.email}: {str(e)}")
        
        return Response({
            'message': f'Sync completed. {len(synced)} staff member(s) updated.',
            'synced_count': len(synced),
            'synced_staff': synced
        })
