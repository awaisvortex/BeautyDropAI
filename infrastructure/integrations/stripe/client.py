"""
Stripe API client wrapper
"""
import stripe
from django.conf import settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


# Stripe Price IDs - These should be configured in your Stripe Dashboard
STRIPE_PRICE_IDS = {
    'basic': 'price_basic_monthly',  # Replace with actual Stripe price ID
    'premium': 'price_premium_monthly',  # Replace with actual Stripe price ID
    'enterprise': 'price_enterprise_monthly',  # Replace with actual Stripe price ID
}


class StripeClient:
    """
    Wrapper for Stripe API client
    """
    
    @staticmethod
    def create_customer(email: str, name: str = None, metadata: Dict[str, Any] = None) -> Optional[stripe.Customer]:
        """
        Create a Stripe customer
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata
            
        Returns:
            Stripe Customer object or None
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            return None
    
    @staticmethod
    def create_checkout_session(
        customer_email: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[stripe.checkout.Session]:
        """
        Create a Stripe Checkout session
        
        Args:
            customer_email: Customer email
            price_id: Stripe price ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
            customer_id: Existing Stripe customer ID (optional)
            metadata: Additional metadata
            
        Returns:
            Stripe Checkout Session object or None
        """
        try:
            params = {
                'mode': 'subscription',
                'line_items': [{
                    'price': price_id,
                    'quantity': 1,
                }],
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': metadata or {},
            }
            
            if customer_id:
                params['customer'] = customer_id
            else:
                params['customer_email'] = customer_email
            
            session = stripe.checkout.Session.create(**params)
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return None
    
    @staticmethod
    def create_subscription(
        customer_id: str,
        price_id: str,
        trial_days: int = None
    ) -> Optional[stripe.Subscription]:
        """
        Create a subscription
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            trial_days: Number of trial days
            
        Returns:
            Stripe Subscription object or None
        """
        try:
            params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
            }
            
            if trial_days:
                params['trial_period_days'] = trial_days
            
            subscription = stripe.Subscription.create(**params)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return None
    
    @staticmethod
    def cancel_subscription(subscription_id: str) -> bool:
        """
        Cancel a subscription
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return False
    
    @staticmethod
    def create_payment_intent(
        amount: int,
        currency: str = 'usd',
        customer_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[stripe.PaymentIntent]:
        """
        Create a payment intent
        
        Args:
            amount: Amount in cents
            currency: Currency code
            customer_id: Stripe customer ID
            metadata: Additional metadata
            
        Returns:
            Stripe PaymentIntent object or None
        """
        try:
            params = {
                'amount': amount,
                'currency': currency,
                'metadata': metadata or {}
            }
            
            if customer_id:
                params['customer'] = customer_id
            
            payment_intent = stripe.PaymentIntent.create(**params)
            return payment_intent
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return None
    
    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
        """
        Get subscription details
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            Stripe Subscription object or None
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving subscription: {str(e)}")
            return None


# Singleton instance
stripe_client = StripeClient()
