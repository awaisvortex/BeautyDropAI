"""
Application-wide constants
"""

# User roles
USER_ROLE_CLIENT = 'client'
USER_ROLE_CUSTOMER = 'customer'
USER_ROLE_STAFF = 'staff'

USER_ROLES = [
    (USER_ROLE_CLIENT, 'Client'),
    (USER_ROLE_CUSTOMER, 'Customer'),
    (USER_ROLE_STAFF, 'Staff'),
]

# Staff invitation statuses
INVITE_STATUS_PENDING = 'pending'
INVITE_STATUS_SENT = 'sent'
INVITE_STATUS_ACCEPTED = 'accepted'
INVITE_STATUS_EXPIRED = 'expired'

INVITE_STATUSES = [
    (INVITE_STATUS_PENDING, 'Pending'),
    (INVITE_STATUS_SENT, 'Sent'),
    (INVITE_STATUS_ACCEPTED, 'Accepted'),
    (INVITE_STATUS_EXPIRED, 'Expired'),
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

# Subscription statuses (matching Stripe)
SUBSCRIPTION_STATUS_ACTIVE = 'active'
SUBSCRIPTION_STATUS_PAST_DUE = 'past_due'
SUBSCRIPTION_STATUS_CANCELED = 'canceled'
SUBSCRIPTION_STATUS_UNPAID = 'unpaid'
SUBSCRIPTION_STATUS_TRIALING = 'trialing'

# Backwards compatibility
SUBSCRIPTION_STATUS_TRIAL = SUBSCRIPTION_STATUS_TRIALING

SUBSCRIPTION_STATUSES = [
    (SUBSCRIPTION_STATUS_ACTIVE, 'Active'),
    (SUBSCRIPTION_STATUS_PAST_DUE, 'Past Due'),
    (SUBSCRIPTION_STATUS_CANCELED, 'Canceled'),
    (SUBSCRIPTION_STATUS_UNPAID, 'Unpaid'),
    (SUBSCRIPTION_STATUS_TRIALING, 'Trialing'),
]

# Subscription plans (deprecated - using SubscriptionPlan model)
PLAN_FREE = 'free'
PLAN_BASIC = 'basic'
PLAN_PREMIUM = 'premium'

SUBSCRIPTION_PLANS = [
    (PLAN_FREE, 'Free'),
    (PLAN_BASIC, 'Basic'),
    (PLAN_PREMIUM, 'Premium'),
]

# Payment statuses (matching Stripe)
PAYMENT_STATUS_SUCCEEDED = 'succeeded'
PAYMENT_STATUS_PENDING = 'pending'
PAYMENT_STATUS_FAILED = 'failed'
PAYMENT_STATUS_REFUNDED = 'refunded'

PAYMENT_STATUSES = [
    (PAYMENT_STATUS_SUCCEEDED, 'Succeeded'),
    (PAYMENT_STATUS_PENDING, 'Pending'),
    (PAYMENT_STATUS_FAILED, 'Failed'),
    (PAYMENT_STATUS_REFUNDED, 'Refunded'),
]

# Webhook sources
WEBHOOK_SOURCE_STRIPE = 'stripe'
WEBHOOK_SOURCE_CLERK = 'clerk'

WEBHOOK_SOURCES = [
    (WEBHOOK_SOURCE_STRIPE, 'Stripe'),
    (WEBHOOK_SOURCE_CLERK, 'Clerk'),
]

# Booking payment statuses (for advance deposits)
BOOKING_PAYMENT_NOT_REQUIRED = 'not_required'
BOOKING_PAYMENT_PENDING = 'pending'
BOOKING_PAYMENT_PAID = 'paid'
BOOKING_PAYMENT_REFUNDED = 'refunded'
BOOKING_PAYMENT_FAILED = 'failed'

BOOKING_PAYMENT_STATUSES = [
    (BOOKING_PAYMENT_NOT_REQUIRED, 'Not Required'),
    (BOOKING_PAYMENT_PENDING, 'Payment Pending'),
    (BOOKING_PAYMENT_PAID, 'Deposit Paid'),
    (BOOKING_PAYMENT_REFUNDED, 'Refunded'),
    (BOOKING_PAYMENT_FAILED, 'Payment Failed'),
]
