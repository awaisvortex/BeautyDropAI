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
    
    @staticmethod
    def create_billing_portal_session(customer_id: str, return_url: str) -> Optional[stripe.billing_portal.Session]:
        """
        Create a billing portal session for subscription management.
        
        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to from portal
            
        Returns:
            Stripe BillingPortal Session object or None
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Error creating billing portal session: {str(e)}")
            return None
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str, webhook_secret: str = None):
        """
        Verify Stripe webhook signature.
        
        Args:
            payload: Raw request body (bytes)
            signature: Stripe-Signature header value
            webhook_secret: Webhook signing secret
            
        Returns:
            Stripe Event object if valid
            
        Raises:
            stripe.error.SignatureVerificationError: If signature is invalid
        """
        if not webhook_secret:
            webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
        logger.info(f"Webhook secret being used: {webhook_secret[:20]}...")
        logger.info(f"Signature header: {signature[:50]}...")
        
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
        return event
    
    @staticmethod
    def update_subscription(subscription_id: str, new_price_id: str) -> Optional[stripe.Subscription]:
        """
        Update subscription to new price/plan.
        
        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New Stripe price ID
            
        Returns:
            Updated Stripe Subscription object or None
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations',
            )
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as e:
            logger.error(f"Error updating subscription: {str(e)}")
            return None
    
    @staticmethod
    def cancel_at_period_end(subscription_id: str) -> Optional[stripe.Subscription]:
        """
        Set subscription to cancel at period end.
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            Updated Stripe Subscription object or None
        """
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Error setting cancel_at_period_end: {str(e)}")
            return None

    @staticmethod
    def get_price_details(price_id: str) -> Optional[Dict[str, Any]]:
        """
        Get price and product details from Stripe.
        
        Args:
            price_id: Stripe price ID
            
        Returns:
            Dictionary with price and product details or None
        """
        try:
            price = stripe.Price.retrieve(price_id, expand=['product'])
            
            return {
                'id': price.id,
                'amount': price.unit_amount / 100.0,  # Convert cents to dollars
                'currency': price.currency,
                'interval': price.recurring.interval,
                'product_id': price.product.id,
                'product_name': price.product.name,
                'product_description': price.product.description,
                'active': price.active and price.product.active
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving price details: {str(e)}")
            return None


# Singleton instance
stripe_client = StripeClient()
