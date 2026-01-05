"""
Stripe Connect API client for marketplace payments.

This module handles:
- Creating Express Connect accounts for salon owners
- Generating onboarding links
- Checking account status
- Creating PaymentIntents with transfers to connected accounts
"""
import stripe
from django.conf import settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeConnectClient:
    """
    Client for Stripe Connect operations.
    
    Used to onboard salon owners and process payments on their behalf.
    """
    
    @staticmethod
    def create_express_account(
        email: str,
        business_name: str = None,
        country: str = 'US',
        metadata: Dict[str, Any] = None
    ) -> Optional[stripe.Account]:
        """
        Create a Stripe Express Connect account for a salon owner.
        
        Express accounts are the easiest for owners to set up -
        Stripe handles identity verification and tax forms.
        
        Args:
            email: Owner's email address
            business_name: Business/salon name
            country: Two-letter country code (default: US)
            metadata: Additional data to store with account
            
        Returns:
            Stripe Account object or None if failed
        """
        try:
            account = stripe.Account.create(
                type='express',
                country=country,
                email=email,
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True},
                },
                business_profile={
                    'name': business_name,
                    'product_description': 'Beauty salon services',
                },
                metadata=metadata or {}
            )
            logger.info(f"Created Stripe Connect account {account.id} for {email}")
            return account
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Connect account: {str(e)}")
            return None
    
    @staticmethod
    def create_account_link(
        account_id: str,
        return_url: str,
        refresh_url: str
    ) -> Optional[str]:
        """
        Create an onboarding link for the salon owner.
        
        This URL takes the owner through Stripe's onboarding flow
        where they verify identity and connect their bank account.
        
        Args:
            account_id: Stripe account ID (acct_xxx)
            return_url: URL to redirect to after onboarding completes
            refresh_url: URL to redirect to if onboarding expires
            
        Returns:
            Onboarding URL string or None if failed
        """
        try:
            account_link = stripe.AccountLink.create(
                account=account_id,
                return_url=return_url,
                refresh_url=refresh_url,
                type='account_onboarding',
            )
            return account_link.url
        except stripe.error.StripeError as e:
            logger.error(f"Error creating account link: {str(e)}")
            return None
    
    @staticmethod
    def create_login_link(account_id: str) -> Optional[str]:
        """
        Create a link to the owner's Express Dashboard.
        
        Allows owners to view their earnings, payouts, and settings.
        
        Args:
            account_id: Stripe account ID (acct_xxx)
            
        Returns:
            Dashboard URL string or None if failed
        """
        try:
            login_link = stripe.Account.create_login_link(account_id)
            return login_link.url
        except stripe.error.StripeError as e:
            logger.error(f"Error creating login link: {str(e)}")
            return None
    
    @staticmethod
    def get_account(account_id: str) -> Optional[stripe.Account]:
        """
        Retrieve account details from Stripe.
        
        Args:
            account_id: Stripe account ID (acct_xxx)
            
        Returns:
            Stripe Account object or None if failed
        """
        try:
            return stripe.Account.retrieve(account_id)
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving account: {str(e)}")
            return None
    
    @staticmethod
    def get_account_status(account_id: str) -> Dict[str, Any]:
        """
        Get detailed status of a Connect account.
        
        Args:
            account_id: Stripe account ID (acct_xxx)
            
        Returns:
            Dictionary with account status details
        """
        try:
            account = stripe.Account.retrieve(account_id)
            return {
                'account_id': account.id,
                'charges_enabled': account.charges_enabled,
                'payouts_enabled': account.payouts_enabled,
                'details_submitted': account.details_submitted,
                'requirements': {
                    'currently_due': account.requirements.currently_due if account.requirements else [],
                    'eventually_due': account.requirements.eventually_due if account.requirements else [],
                    'pending_verification': account.requirements.pending_verification if account.requirements else [],
                },
                'business_type': account.business_type,
                'email': account.email,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error getting account status: {str(e)}")
            return {
                'error': str(e),
                'charges_enabled': False,
                'payouts_enabled': False,
            }
    
    @staticmethod
    def create_payment_intent_with_transfer(
        amount: int,
        currency: str = 'usd',
        destination_account_id: str = None,
        customer_id: str = None,
        metadata: Dict[str, Any] = None,
        application_fee_amount: int = 0
    ) -> Optional[stripe.PaymentIntent]:
        """
        Create a PaymentIntent that transfers funds to a connected account.
        
        This is used for advance booking deposits - the customer pays,
        and the funds go directly to the salon owner's account.
        
        Args:
            amount: Amount in cents (e.g., 1000 = $10.00)
            currency: Currency code (default: usd)
            destination_account_id: Connected account to receive funds (acct_xxx)
            customer_id: Stripe customer ID for saved payment methods
            metadata: Additional data (e.g., booking_id)
            application_fee_amount: Platform fee in cents (optional)
            
        Returns:
            Stripe PaymentIntent object or None if failed
        """
        try:
            params = {
                'amount': amount,
                'currency': currency,
                'metadata': metadata or {},
                # Disable redirect-based payment methods (Klarna, etc.)
                # This allows CLI testing and card-only payments
                'automatic_payment_methods': {
                    'enabled': True,
                    'allow_redirects': 'never',
                },
            }
            
            # Add customer for saved payment methods
            if customer_id:
                params['customer'] = customer_id
            
            # Add transfer to connected account
            if destination_account_id:
                params['transfer_data'] = {
                    'destination': destination_account_id,
                }
                # Optional: Take a platform fee
                if application_fee_amount > 0:
                    params['application_fee_amount'] = application_fee_amount
            
            payment_intent = stripe.PaymentIntent.create(**params)
            logger.info(f"Created PaymentIntent {payment_intent.id} for ${amount/100:.2f}")
            return payment_intent
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return None
    
    @staticmethod
    def refund_payment(
        payment_intent_id: str,
        amount: int = None,
        reason: str = 'requested_by_customer'
    ) -> Optional[stripe.Refund]:
        """
        Refund a payment (full or partial).
        
        Used when a booking is cancelled and deposit needs to be returned.
        
        Args:
            payment_intent_id: PaymentIntent ID (pi_xxx)
            amount: Amount to refund in cents (None = full refund)
            reason: Reason for refund
            
        Returns:
            Stripe Refund object or None if failed
        """
        try:
            params = {
                'payment_intent': payment_intent_id,
                'reason': reason,
            }
            if amount:
                params['amount'] = amount
            
            refund = stripe.Refund.create(**params)
            logger.info(f"Refunded PaymentIntent {payment_intent_id}")
            return refund
        except stripe.error.StripeError as e:
            logger.error(f"Error refunding payment: {str(e)}")
            return None


# Singleton instance
stripe_connect_client = StripeConnectClient()
