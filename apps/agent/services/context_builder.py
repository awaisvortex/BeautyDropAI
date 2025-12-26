"""
Context builder for AI agent.
Builds role-specific context and retrieves relevant knowledge from Pinecone.
"""
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from datetime import timedelta

from .embedding_service import EmbeddingService
from .pinecone_service import PineconeService

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds context for the AI agent based on user role.
    Retrieves relevant knowledge from Pinecone for RAG.
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.pinecone_service = PineconeService()
    
    def build_context(self, user, role: str, session=None) -> Dict[str, Any]:
        """
        Build complete context object based on user role.
        
        Args:
            user: User instance (can be None for guests)
            role: User role (customer, client, staff, guest)
            session: Optional ChatSession for additional context
            
        Returns:
            Context dictionary
        """
        context = {
            "user_info": self._get_user_info(user) if user else {"name": "Guest"},
            "current_datetime": timezone.now().isoformat(),
            "role": role,
        }
        
        if role == 'guest':
            # Guest users get minimal context
            context['is_authenticated'] = False
        elif role == 'customer':
            context['is_authenticated'] = True
            context.update(self._build_customer_context(user))
        elif role == 'client':
            context['is_authenticated'] = True
            context.update(self._build_owner_context(user))
        elif role == 'staff':
            context['is_authenticated'] = True
            context.update(self._build_staff_context(user))
        
        # Add conversation-specific context
        if session and session.current_shop:
            context["current_shop"] = self._get_shop_summary(session.current_shop)
        
        return context
    
    def _get_user_info(self, user) -> Dict[str, Any]:
        """Get basic user information."""
        return {
            "name": user.full_name or user.email,
            "email": user.email,
        }
    
    def _build_customer_context(self, user) -> Dict[str, Any]:
        """Build context for customer users."""
        from apps.customers.models import Customer
        from apps.bookings.models import Booking
        
        context = {}
        
        try:
            customer = Customer.objects.get(user=user)
            
            # Upcoming bookings
            upcoming = Booking.objects.filter(
                customer=customer,
                booking_datetime__gte=timezone.now(),
                status__in=['pending', 'confirmed']
            ).select_related('shop', 'service').order_by('booking_datetime')[:5]
            
            context['upcoming_bookings'] = [
                {
                    "id": str(b.id),
                    "shop": b.shop.name,
                    "service": b.service.name,
                    "datetime": b.booking_datetime.isoformat(),
                    "status": b.status
                }
                for b in upcoming
            ]
            
            # Recent bookings
            recent = Booking.objects.filter(
                customer=customer,
                status='completed'
            ).select_related('shop', 'service').order_by('-booking_datetime')[:3]
            
            context['recent_bookings'] = [
                {
                    "shop": b.shop.name,
                    "service": b.service.name,
                    "date": b.booking_datetime.date().isoformat()
                }
                for b in recent
            ]
            
            # Favorite shops
            favorites = customer.favorite_shops.filter(is_active=True)[:5]
            context['favorite_shops'] = [
                {"id": str(s.id), "name": s.name}
                for s in favorites
            ]
            
        except Customer.DoesNotExist:
            context['upcoming_bookings'] = []
            context['recent_bookings'] = []
            context['favorite_shops'] = []
        
        return context
    
    def _build_owner_context(self, user) -> Dict[str, Any]:
        """Build context for shop owner users."""
        from apps.clients.models import Client
        from apps.bookings.models import Booking
        
        context = {}
        
        try:
            client = Client.objects.get(user=user)
            shops = client.shops.filter(is_active=True)
            
            if shops.exists():
                shop = shops.first()  # Primary shop
                context['shop_info'] = self._get_shop_summary(shop)
                
                # Staff members
                staff = shop.staff_members.filter(is_active=True)
                context['staff'] = [
                    {"id": str(s.id), "name": s.name, "email": s.email}
                    for s in staff[:10]
                ]
                
                # Today's bookings
                today = timezone.now().date()
                today_bookings = Booking.objects.filter(
                    shop=shop,
                    booking_datetime__date=today
                ).select_related('customer__user', 'service', 'staff_member').order_by('booking_datetime')
                
                context['today_bookings'] = [
                    {
                        "id": str(b.id),
                        "customer": b.customer.user.full_name,
                        "service": b.service.name,
                        "time": b.booking_datetime.strftime("%I:%M %p"),
                        "staff": b.staff_member.name if b.staff_member else "Unassigned",
                        "status": b.status
                    }
                    for b in today_bookings
                ]
                
                # Pending bookings count
                pending_count = Booking.objects.filter(
                    shop=shop,
                    status='pending'
                ).count()
                context['pending_bookings_count'] = pending_count
                
                # This week's stats
                week_start = today - timedelta(days=today.weekday())
                week_bookings = Booking.objects.filter(
                    shop=shop,
                    booking_datetime__date__gte=week_start,
                    status__in=['confirmed', 'completed']
                ).count()
                context['bookings_this_week'] = week_bookings
                
        except Client.DoesNotExist:
            context['shop_info'] = None
        
        return context
    
    def _build_staff_context(self, user) -> Dict[str, Any]:
        """Build context for staff users."""
        from apps.staff.models import StaffMember
        from apps.bookings.models import Booking
        
        context = {}
        
        try:
            staff = StaffMember.objects.select_related('shop').get(user=user)
            
            context['shop_info'] = {
                "id": str(staff.shop.id),
                "name": staff.shop.name,
                "phone": staff.shop.phone
            }
            
            # Services they provide
            services = staff.services.filter(is_active=True)
            context['my_services'] = [
                {"id": str(s.id), "name": s.name}
                for s in services
            ]
            
            # Today's assigned bookings
            today = timezone.now().date()
            today_bookings = Booking.objects.filter(
                staff_member=staff,
                booking_datetime__date=today
            ).select_related('customer__user', 'service').order_by('booking_datetime')
            
            context['today_bookings'] = [
                {
                    "id": str(b.id),
                    "customer": b.customer.user.full_name,
                    "service": b.service.name,
                    "time": b.booking_datetime.strftime("%I:%M %p"),
                    "status": b.status
                }
                for b in today_bookings
            ]
            
            # Upcoming this week
            week_end = today + timedelta(days=7)
            upcoming = Booking.objects.filter(
                staff_member=staff,
                booking_datetime__date__gt=today,
                booking_datetime__date__lte=week_end,
                status__in=['pending', 'confirmed']
            ).count()
            context['upcoming_bookings_count'] = upcoming
            
        except StaffMember.DoesNotExist:
            context['shop_info'] = None
        
        return context
    
    def _get_shop_summary(self, shop) -> Dict[str, Any]:
        """Get shop summary for context."""
        return {
            "id": str(shop.id),
            "name": shop.name,
            "address": shop.address,
            "city": shop.city,
            "phone": shop.phone,
            "timezone": shop.timezone,
            "rating": float(shop.average_rating),
            "is_verified": shop.is_verified
        }
    
    def get_relevant_knowledge(self, query: str, top_k: int = 3) -> Optional[str]:
        """
        Retrieve relevant shop/service information from Pinecone.
        
        Args:
            query: User's query text
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string or None
        """
        try:
            # Generate embedding for query
            embedding = self.embedding_service.get_embedding(query)
            
            # Query shops namespace
            shop_results = self.pinecone_service.query(
                embedding=embedding,
                namespace=PineconeService.NAMESPACE_SHOPS,
                top_k=top_k,
                min_score=0.6
            )
            
            if not shop_results:
                return None
            
            # Format results
            context_parts = []
            for result in shop_results:
                meta = result['metadata']
                context_parts.append(
                    f"Shop: {meta.get('shop_name', 'Unknown')}\n"
                    f"Location: {meta.get('city', '')}, {meta.get('state', '')}\n"
                    f"Services: {meta.get('services', '')}\n"
                    f"Rating: {meta.get('rating', 'N/A')}/5 ({meta.get('total_reviews', 0)} reviews)\n"
                    f"Shop ID: {meta.get('shop_id', '')}"
                )
            
            return "\n\n---\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {e}")
            return None
