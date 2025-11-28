"""
Custom AutoSchema for automatic tag assignment
"""
from drf_spectacular.openapi import AutoSchema


class CustomAutoSchema(AutoSchema):
    """
    Custom schema that automatically assigns tags based on ViewSet and action
    """
    
    def get_tags(self):
        """Auto-assign tags based on ViewSet class and action"""
        tags = super().get_tags()
        
        if tags:
            return tags
        
        # Get the viewset class name
        view = self.view
        view_name = view.__class__.__name__
        action = getattr(view, 'action', None)
        
        # Map ViewSets to tags
        tag_mapping = {
            'ServiceViewSet': self._get_service_tag(action),
            'ShopViewSet': self._get_shop_tag(action),
            'ShopScheduleViewSet': ['Schedules - Client'],
            'TimeSlotViewSet': self._get_timeslot_tag(action),
            'BookingViewSet': self._get_booking_tag(action),
            'SubscriptionViewSet': ['Payments - Customer'],
            'PaymentViewSet': self._get_payment_tag(action),
        }
        
        return tag_mapping.get(view_name, ['api'])
    
    def _get_service_tag(self, action):
        """Get tag for service endpoints"""
        client_actions = ['create', 'update', 'partial_update', 'destroy', 'toggle_active']
        if action in client_actions:
            return ['Services - Client']
        return ['Services - Public']
    
    def _get_shop_tag(self, action):
        """Get tag for shop endpoints"""
        public_actions = ['search', 'public']
        client_actions = ['create', 'update', 'partial_update', 'destroy', 'my_shops', 'toggle_active', 'dashboard']
        
        if action in public_actions:
            return ['Shops - Public']
        elif action in client_actions:
            return ['Shops - Client']
        return ['Shops - Public']
    
    def _get_timeslot_tag(self, action):
        """Get tag for time slot endpoints"""
        public_actions = ['check_availability']
        if action in public_actions:
            return ['Schedules - Public']
        return ['Schedules - Client']
    
    def _get_booking_tag(self, action):
        """Get tag for booking endpoints"""
        customer_actions = ['create', 'my_bookings', 'cancel', 'reschedule']
        client_actions = ['shop_bookings', 'today_bookings', 'upcoming_bookings', 'confirm', 'complete', 'no_show', 'stats']
        
        if action in customer_actions:
            return ['Bookings - Customer']
        elif action in client_actions:
            return ['Bookings - Client']
        return ['Bookings - Customer']
    
    def _get_payment_tag(self, action):
        """Get tag for payment endpoints"""
        return ['Payments - Customer']
