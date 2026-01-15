"""
User-friendly messages for API responses.

These messages are designed to be:
- Simple and jargon-free
- Actionable with clear next steps
- Helpful for non-technical users
"""

# ============================================
# Stripe Connect Messages
# ============================================

STRIPE_CONNECT = {
    # Account creation
    'not_shop_owner': {
        'error': "You need to be a salon owner to set up payments.",
        'message': "This feature is only available for salon owners who have created a shop.",
        'next_steps': "If you're a salon owner, please create your shop first from the dashboard."
    },
    'create_failed': {
        'error': "We couldn't set up your payment account right now.",
        'message': "There was a problem connecting to our payment provider.",
        'next_steps': "Please try again in a few minutes. If the problem continues, contact support."
    },
    'already_exists': {
        'message': "You already have a payment account set up.",
        'next_steps': "Visit your earnings page to manage your payment settings."
    },
    
    # Onboarding
    'no_account': {
        'error': "You haven't set up payments yet.",
        'message': "Before you can receive payments, you need to create a payment account.",
        'next_steps': "Click 'Set Up Payments' to get started. It only takes a few minutes."
    },
    'onboarding_complete': {
        'message': "Great news! Your payment setup is complete.",
        'next_steps': "You can now receive advance payments from customers when they book."
    },
    'onboarding_link_failed': {
        'error': "We couldn't open the payment setup page.",
        'message': "There was a problem loading the setup form.",
        'next_steps': "Please refresh the page and try again."
    },
    
    # Dashboard
    'dashboard_link_failed': {
        'error': "We couldn't open your payment dashboard.",
        'message': "There was a problem connecting to your payment account.",
        'next_steps': "Please try again in a moment."
    },
}

# ============================================
# Google Calendar Messages
# ============================================

CALENDAR = {
    'not_connected_clerk': {
        'error': "Your Google account is not connected.",
        'message': "To sync your bookings with Google Calendar, you need to sign in with Google first.",
        'next_steps': [
            "1. Go to your account settings",
            "2. Click 'Connect with Google'",
            "3. Allow access to your calendar",
            "4. Return here and try again"
        ]
    },
    'missing_calendar_permission': {
        'error': "We don't have permission to access your calendar.",
        'message': "Your Google account is connected, but calendar access wasn't granted.",
        'next_steps': [
            "1. Sign out of your account",
            "2. Sign back in using Google",
            "3. When asked, check the box to allow calendar access",
            "4. Try connecting again"
        ]
    },
    'api_verification_failed': {
        'error': "We couldn't connect to Google Calendar.",
        'message': "Your permissions look correct, but we couldn't reach Google's servers.",
        'next_steps': "Please try again in a few moments. If this continues, try signing out and back in."
    },
    'not_connected': {
        'error': "Google Calendar is not connected.",
        'message': "You need to connect your Google Calendar first before you can sync or view calendars.",
        'next_steps': "Click 'Connect Google Calendar' to get started."
    },
    'token_refresh_failed': {
        'error': "Your Google connection has expired.",
        'message': "We need you to reconnect your Google account.",
        'next_steps': "Click 'Reconnect Google' to restore calendar sync."
    },
    'no_integration': {
        'error': "Calendar sync is not set up yet.",
        'message': "You haven't connected a calendar for syncing.",
        'next_steps': "Connect your Google Calendar to automatically sync your bookings."
    },
}

# ============================================
# Booking Messages  
# ============================================

BOOKING = {
    'shop_closed': {
        'error': "The salon is closed on this date.",
        'message': "This shop doesn't have availability on the date you selected.",
        'next_steps': "Please choose a different date when the salon is open."
    },
    'slot_not_available': {
        'error': "This time slot is no longer available.",
        'message': "Someone may have just booked this slot, or it's outside business hours.",
        'next_steps': "Please select a different time from the available slots."
    },
    'no_staff_for_service': {
        'error': "No staff available for this service.",
        'message': "This service doesn't have any staff members assigned to it yet.",
        'next_steps': "Please contact the salon directly or try a different service."
    },
    'staff_not_available': {
        'error': "This staff member is not available at the selected time.",
        'message': "The stylist you selected is busy at this time.",
        'next_steps': "Choose a different time or select 'Any available staff'."
    },
    'payment_expired': {
        'error': "Your booking reservation has expired.",
        'message': "The 15-minute payment window has passed.",
        'next_steps': "Please start a new booking. The time slot may still be available."
    },
    'already_cancelled': {
        'error': "This booking has already been cancelled.",
        'message': "No further action is needed for this booking."
    },
    'cannot_cancel': {
        'error': "This booking cannot be cancelled.",
        'message': "Completed or past bookings cannot be cancelled.",
        'next_steps': "If you have concerns, please contact the salon directly."
    },
    'payment_required': {
        'error': "Payment is required to confirm this booking.",
        'message': "The salon requires an advance payment to hold your spot.",
        'next_steps': "Complete the payment within 15 minutes to confirm your booking."
    },
}

# ============================================
# Profile & Authentication Messages
# ============================================

PROFILE = {
    'customer_not_found': {
        'error': "Your customer profile wasn't found.",
        'message': "It looks like your account setup isn't complete.",
        'next_steps': "Please contact support to complete your account setup."
    },
    'client_not_found': {
        'error': "Your salon owner profile wasn't found.",
        'message': "Your account isn't set up as a salon owner.",
        'next_steps': "If you're a salon owner, please complete your business registration."
    },
    'staff_not_found': {
        'error': "Your staff profile wasn't found.",
        'message': "Your account isn't linked to a salon.",
        'next_steps': "Please ask your salon manager to add you as a staff member."
    },
    'unauthorized': {
        'error': "You don't have permission to do this.",
        'message': "This action requires different account permissions.",
        'next_steps': "Please log in with the correct account or contact your admin."
    },
}

# ============================================
# Shop & Service Messages
# ============================================

SHOP = {
    'not_found': {
        'error': "Salon not found.",
        'message': "We couldn't find this salon. It may have been removed or the link is incorrect.",
        'next_steps': "Please check the link or search for salons in your area."
    },
    'not_active': {
        'error': "This salon is currently unavailable.",
        'message': "The salon has temporarily paused their services.",
        'next_steps': "Please try again later or browse other salons."
    },
    'already_favorite': {
        'error': "Already in your favorites.",
        'message': "This salon is already saved to your favorites list."
    },
    'not_in_favorites': {
        'error': "Not in your favorites.",
        'message': "This salon isn't in your favorites list."
    },
}

SERVICE = {
    'not_found': {
        'error': "Service not found.",
        'message': "This service may no longer be available.",
        'next_steps': "Please browse available services at this salon."
    },
    'not_active': {
        'error': "This service is currently unavailable.",
        'message': "The salon has temporarily paused this service.",
        'next_steps': "Please choose a different service or check back later."
    },
}

# ============================================
# Staff Messages
# ============================================

STAFF = {
    'not_found': {
        'error': "Staff member not found.",
        'message': "This stylist may no longer work at this salon.",
        'next_steps': "Please select a different staff member or choose 'Any available'."
    },
    'cannot_provide_service': {
        'error': "This stylist doesn't offer this service.",
        'message': "The selected staff member isn't trained for this service.",
        'next_steps': "Please select a different stylist or choose 'Any available'."
    },
    'has_bookings': {
        'error': "Cannot remove staff with upcoming bookings.",
        'message': "This staff member has appointments that need to be reassigned first.",
        'next_steps': "Reassign or cancel their upcoming bookings before removing them."
    },
}

# ============================================
# General Messages
# ============================================

GENERAL = {
    'server_error': {
        'error': "Something went wrong on our end.",
        'message': "We're sorry, but we couldn't complete your request.",
        'next_steps': "Please try again in a few moments. If this continues, contact support."
    },
    'invalid_request': {
        'error': "We couldn't understand your request.",
        'message': "Some required information is missing or incorrect.",
        'next_steps': "Please check your input and try again."
    },
    'not_found': {
        'error': "Not found.",
        'message': "We couldn't find what you're looking for.",
        'next_steps': "Please check the link or go back to the previous page."
    },
}
