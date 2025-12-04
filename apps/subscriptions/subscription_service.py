"""
Subscription service layer for managing subscription business logic.

This module provides high-level functions for:
- Validating subscription upgrade/downgrade eligibility
- Creating and managing subscriptions
- Enforcing subscription rules
- Syncing with Stripe subscription data
"""
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.subscriptions.models import Subscription, SubscriptionPlan, SubscriptionHistory

logger = logging.getLogger(__name__)


def get_current_subscription(user):
    """
    Get user's current active subscription.
    
    Args:
        user: User instance
        
    Returns:
        Subscription instance or None
    """
    return Subscription.objects.filter(
        user=user,
        is_current=True,
        status='active'
    ).select_related('plan').first()


def can_subscribe_to_plan(user, new_plan):
    """
    Validate if user can subscribe to a plan.
    
    Business Rules:
    - New subscription: Always allowed
    - Upgrade (higher price): Allowed
    - Downgrade (lower price): Blocked -must cancel first
    - Same tier: Blocked - already subscribed
    
    Args:
        user: User instance
        new_plan: SubscriptionPlan instance
        
    Returns:
        tuple: (can_subscribe: bool, action: str, message: str)
    """
    current_sub = get_current_subscription(user)
    
    # No current subscription - allow
    if not current_sub:
        return True, "new", f"Subscribing to {new_plan.name}"
    
    current_amount = current_sub.plan.amount
    new_amount = new_plan.amount
    
    # Upgrade - allowed
    if new_amount > current_amount:
        return True, "upgrade", f"Upgrading to {new_plan.name}"
    
    # Downgrade - blocked
    elif new_amount < current_amount:
        return (
            False,
            "downgrade",
            "Please cancel your current subscription before downgrading"
        )
    
    # Same tier - blocked
    else:
        return (
            False,
            "same_tier",
            f"You already have the {new_plan.name} plan. Please unsubscribe first to resubscribe."
        )


@transaction.atomic
def create_subscription_from_stripe(user, plan, stripe_subscription_data):
    """
    Create subscription from Stripe subscription data.
    
    Handles upgrade logic if user already has a subscription.
    
    Args:
        user: User instance
        plan: SubscriptionPlan instance
        stripe_subscription_data: Stripe subscription object (dict)
        
    Returns:
        Subscription instance
    """
    from datetime import datetime
    
    current_sub = get_current_subscription(user)
    
    # Handle upgrade scenario
    if current_sub and plan.amount > current_sub.plan.amount:
        logger.info(f"Upgrading subscription for {user.email} from {current_sub.plan.name} to {plan.name}")
        
        # Mark old subscription as non-current
        current_sub.is_current = False
        current_sub.cancel_at_period_end = True
        current_sub.save()
        
        # Log upgrade in history
        SubscriptionHistory.objects.create(
            subscription=current_sub,
            action='upgraded',
            old_plan=current_sub.plan,
            new_plan=plan,
            reason='User upgraded to higher tier'
        )
    
    # Create new subscription
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id=stripe_subscription_data['id'],
        stripe_customer_id=stripe_subscription_data['customer'],
        status=stripe_subscription_data['status'],
        is_current=True,
        current_period_start=datetime.fromtimestamp(
            stripe_subscription_data['current_period_start'],
            tz=timezone.utc
        ),
        current_period_end=datetime.fromtimestamp(
            stripe_subscription_data['current_period_end'],
            tz=timezone.utc
        ),
        cancel_at_period_end=stripe_subscription_data.get('cancel_at_period_end', False)
    )
    
    # Log creation in history
    SubscriptionHistory.objects.create(
        subscription=subscription,
        action='created',
        new_plan=plan,
        reason='Subscription created'
    )
    
    logger.info(f"Created subscription {subscription.id} for {user.email}")
    return subscription


@transaction.atomic
def deactivate_subscription(subscription):
    """
    Deactivate subscription and all shops owned by the user.
    
    Args:
        subscription: Subscription instance
    """
    subscription.is_current = False
    subscription.status = 'canceled'
    subscription.cancelled_at = timezone.now()
    subscription.save()
    
    # Deactivate all shops for this client
    try:
        client = subscription.user.client_profile
        deactivated_count = client.shops.filter(is_active=True).update(is_active=False)
        logger.info(f"Deactivated {deactivated_count} shops for canceled subscription {subscription.id}")
    except Exception as e:
        logger.error(f"Error deactivating shops: {str(e)}")
    
    # Log in history
    SubscriptionHistory.objects.create(
        subscription=subscription,
        action='cancelled',
        reason='Subscription deactivated'
    )


def can_activate_shop(client):
    """
    Check if client can activate a shop.
    
    Requires an active subscription.
    
    Args:
        client: Client instance
        
    Returns:
        tuple: (can_activate: bool, message: str)
    """
    user = client.user
    current_sub = get_current_subscription(user)
    
    if not current_sub:
        return False, "Active subscription required to activate shops"
    
    if current_sub.status != 'active':
        return False, f"Subscription is {current_sub.status}. Please update payment method."
    
    return True, "OK"


def enforce_subscription_limits(client):
    """
    Enforce subscription limits - deactivate all shops if no active subscription.
    
    Args:
        client: Client instance
    """
    user = client.user
    current_sub = get_current_subscription(user)
    
    if not current_sub or current_sub.status != 'active':
        # Deactivate all shops
        deactivated_count = client.shops.filter(is_active=True).update(is_active=False)
        if deactivated_count > 0:
            logger.warning(f"Deactivated {deactivated_count} shops for {client.business_name} - no active subscription")


def sync_subscription_from_stripe(stripe_subscription_data):
    """
    Sync local subscription from Stripe subscription data.
    
    Args:
        stripe_subscription_data: Stripe subscription object (dict)
        
    Returns:
        Subscription instance or None
    """
    from datetime import datetime
    
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription_data['id']
        )
        
        # Update fields
        subscription.status = stripe_subscription_data['status']
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_subscription_data['current_period_end'],
            tz=timezone.utc
        )
        subscription.cancel_at_period_end = stripe_subscription_data.get('cancel_at_period_end', False)
        subscription.save()
        
        logger.info(f"Synced subscription {subscription.id} from Stripe")
        return subscription
        
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found for Stripe ID: {stripe_subscription_data['id']}")
        return None
