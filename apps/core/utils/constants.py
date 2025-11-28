"""
Application-wide constants
"""

# User roles
USER_ROLE_CLIENT = 'client'
USER_ROLE_CUSTOMER = 'customer'

USER_ROLES = [
    (USER_ROLE_CLIENT, 'Client'),
    (USER_ROLE_CUSTOMER, 'Customer'),
]

# Booking statuses
BOOKING_STATUS_PENDING = 'pending'
BOOKING_STATUS_CONFIRMED = 'confirmed'
BOOKING_STATUS_CANCELLED = 'cancelled'
BOOKING_STATUS_COMPLETED = 'completed'
BOOKING_STATUS_NO_SHOW = 'no_show'

BOOKING_STATUSES = [
    (BOOKING_STATUS_PENDING, 'Pending'),
    (BOOKING_STATUS_CONFIRMED, 'Confirmed'),
    (BOOKING_STATUS_CANCELLED, 'Cancelled'),
    (BOOKING_STATUS_COMPLETED, 'Completed'),
    (BOOKING_STATUS_NO_SHOW, 'No Show'),
]

# Time slot statuses
SLOT_STATUS_AVAILABLE = 'available'
SLOT_STATUS_BOOKED = 'booked'
SLOT_STATUS_BLOCKED = 'blocked'

SLOT_STATUSES = [
    (SLOT_STATUS_AVAILABLE, 'Available'),
    (SLOT_STATUS_BOOKED, 'Booked'),
    (SLOT_STATUS_BLOCKED, 'Blocked'),
]

# Days of week
DAYS_OF_WEEK = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]

# Subscription statuses
SUBSCRIPTION_STATUS_ACTIVE = 'active'
SUBSCRIPTION_STATUS_CANCELLED = 'cancelled'
SUBSCRIPTION_STATUS_EXPIRED = 'expired'
SUBSCRIPTION_STATUS_TRIAL = 'trial'

SUBSCRIPTION_STATUSES = [
    (SUBSCRIPTION_STATUS_ACTIVE, 'Active'),
    (SUBSCRIPTION_STATUS_CANCELLED, 'Cancelled'),
    (SUBSCRIPTION_STATUS_EXPIRED, 'Expired'),
    (SUBSCRIPTION_STATUS_TRIAL, 'Trial'),
]

# Subscription plans
PLAN_FREE = 'free'
PLAN_BASIC = 'basic'
PLAN_PREMIUM = 'premium'

SUBSCRIPTION_PLANS = [
    (PLAN_FREE, 'Free'),
    (PLAN_BASIC, 'Basic'),
    (PLAN_PREMIUM, 'Premium'),
]

# Payment statuses
PAYMENT_STATUS_PENDING = 'pending'
PAYMENT_STATUS_COMPLETED = 'completed'
PAYMENT_STATUS_FAILED = 'failed'
PAYMENT_STATUS_REFUNDED = 'refunded'

PAYMENT_STATUSES = [
    (PAYMENT_STATUS_PENDING, 'Pending'),
    (PAYMENT_STATUS_COMPLETED, 'Completed'),
    (PAYMENT_STATUS_FAILED, 'Failed'),
    (PAYMENT_STATUS_REFUNDED, 'Refunded'),
]
