"""
Booking payment service for advance deposits.

This module handles:
- Calculating advance payment amounts
- Creating PaymentIntents for booking deposits
- Confirming payments and updating booking status
- Refunding deposits on cancellation
"""
from decimal import Decimal
from typing import Dict, Any, Optional
import logging

from django.utils import timezone

from apps.bookings.models import Booking
from apps.shops.models import Shop
from apps.payments.models import ConnectedAccount, BookingPayment
from apps.payments.stripe_connect import stripe_connect_client
from apps.core.utils.constants import (
    BOOKING_PAYMENT_PENDING, BOOKING_PAYMENT_PAID, 
    BOOKING_PAYMENT_REFUNDED, BOOKING_PAYMENT_NOT_REQUIRED,
    BOOKING_STATUS_CONFIRMED
)

logger = logging.getLogger(__name__)


class BookingPaymentService:
    """
    Service for managing booking advance payments.
    """
    
    @staticmethod
    def calculate_advance_amount(service_price: Decimal, shop: Shop) -> Decimal:
        """
        Calculate the advance payment amount based on shop settings.
        
        Args:
            service_price: Total price of the service/deal
            shop: Shop model with advance payment settings
            
        Returns:
            Advance payment amount (Decimal)
        """
        if not shop.advance_payment_enabled:
            return Decimal('0.00')
        
        percentage = shop.advance_payment_percentage
        advance = (service_price * percentage) / Decimal('100')
        
        # Round to 2 decimal places
        return advance.quantize(Decimal('0.01'))
    
    @staticmethod
    def create_advance_payment(booking: Booking) -> Dict[str, Any]:
        """
        Create a PaymentIntent for the booking's advance deposit.
        
        This is called when a booking is created. Returns the client_secret
        for the frontend to complete payment with Stripe.js.
        
        Args:
            booking: Booking model instance
            
        Returns:
            Dictionary with:
            - success: bool
            - client_secret: str (for Stripe.js)
            - amount: Decimal
            - error: str (if failed)
        """
        shop = booking.shop
        
        # Check if advance payment is required
        if not shop.advance_payment_enabled:
            # Mark booking as not requiring payment but keep as pending
            booking.payment_status = BOOKING_PAYMENT_NOT_REQUIRED
            booking.save(update_fields=['payment_status'])
            return {
                'success': True,
                'payment_required': False,
                'message': 'Booking created successfully. Salon owner will confirm your booking shortly.'
            }
        
        # Calculate advance amount
        advance_amount = BookingPaymentService.calculate_advance_amount(
            booking.total_price, shop
        )
        
        if advance_amount <= 0:
            booking.payment_status = BOOKING_PAYMENT_NOT_REQUIRED
            booking.save(update_fields=['payment_status'])
            return {
                'success': True,
                'payment_required': False,
                'message': 'Booking created successfully. Salon owner will confirm your booking shortly.'
            }
        
        # Get connected account for the shop owner
        try:
            connected_account = shop.client.connected_account
            if not connected_account.is_ready_for_payments:
                # Owner hasn't completed onboarding - booking stays pending
                logger.warning(f"Shop {shop.id} owner hasn't completed Stripe onboarding")
                booking.payment_status = BOOKING_PAYMENT_NOT_REQUIRED
                booking.save(update_fields=['payment_status'])
                return {
                    'success': True,
                    'payment_required': False,
                    'message': 'Booking created successfully. Salon owner will confirm your booking shortly.'
                }
            destination_account_id = connected_account.stripe_account_id
        except ConnectedAccount.DoesNotExist:
            # No connected account - booking stays pending
            logger.warning(f"Shop {shop.id} has no connected Stripe account")
            booking.payment_status = BOOKING_PAYMENT_NOT_REQUIRED
            booking.save(update_fields=['payment_status'])
            return {
                'success': True,
                'payment_required': False,
                'message': 'Booking created successfully. Salon owner will confirm your booking shortly.'
            }
        
        # Get customer's Stripe ID if they have one
        customer_stripe_id = None
        try:
            stripe_customer = booking.customer.user.stripe_customer
            customer_stripe_id = stripe_customer.stripe_customer_id
        except Exception:
            pass  # Customer doesn't have a Stripe account yet
        
        # Convert to cents for Stripe
        amount_cents = int(advance_amount * 100)
        
        # Create PaymentIntent with transfer to shop owner
        payment_intent = stripe_connect_client.create_payment_intent_with_transfer(
            amount=amount_cents,
            currency='usd',  # TODO: Make configurable per shop
            destination_account_id=destination_account_id,
            customer_id=customer_stripe_id,
            metadata={
                'booking_id': str(booking.id),
                'shop_id': str(shop.id),
                'customer_id': str(booking.customer.id),
                'type': 'advance_deposit',
            }
        )
        
        if not payment_intent:
            return {
                'success': False,
                'error': 'Failed to create payment intent'
            }
        
        # Calculate payment expiration (15 minutes from now)
        from datetime import timedelta
        payment_expires_at = timezone.now() + timedelta(minutes=15)
        
        # Create BookingPayment record
        BookingPayment.objects.create(
            booking=booking,
            stripe_payment_intent_id=payment_intent.id,
            amount=advance_amount,
            currency='usd',
            destination_account=connected_account,
            status=BOOKING_PAYMENT_PENDING,
            payment_expires_at=payment_expires_at,
            metadata={
                'client_secret': payment_intent.client_secret,
            }
        )
        
        # Update booking payment status
        booking.payment_status = BOOKING_PAYMENT_PENDING
        booking.save(update_fields=['payment_status'])
        
        logger.info(f"Created advance payment for booking {booking.id}: ${advance_amount}")
        
        return {
            'success': True,
            'payment_required': True,
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id,
            'amount': advance_amount,
            'amount_cents': amount_cents,
            'currency': 'usd',
        }
    
    @staticmethod
    def confirm_booking_payment(
        payment_intent_id: str
    ) -> Dict[str, Any]:
        """
        Confirm that a payment was successful and update booking status.
        
        Called by webhook when payment_intent.succeeded is received.
        
        Args:
            payment_intent_id: Stripe PaymentIntent ID (pi_xxx)
            
        Returns:
            Dictionary with success status and booking details
        """
        try:
            booking_payment = BookingPayment.objects.select_related(
                'booking', 'booking__shop', 'booking__customer'
            ).get(stripe_payment_intent_id=payment_intent_id)
        except BookingPayment.DoesNotExist:
            logger.error(f"BookingPayment not found for PI {payment_intent_id}")
            return {
                'success': False,
                'error': 'Payment record not found'
            }
        
        booking = booking_payment.booking
        
        # Update payment record
        booking_payment.status = BOOKING_PAYMENT_PAID
        booking_payment.paid_at = timezone.now()
        booking_payment.save(update_fields=['status', 'paid_at'])
        
        # Update booking status to confirmed
        booking.payment_status = BOOKING_PAYMENT_PAID
        booking.status = BOOKING_STATUS_CONFIRMED
        booking.save(update_fields=['payment_status', 'status'])
        
        logger.info(f"Booking {booking.id} confirmed after payment {payment_intent_id}")
        
        # TODO: Send confirmation notification to customer
        
        return {
            'success': True,
            'booking_id': str(booking.id),
            'amount': booking_payment.amount,
            'shop_name': booking.shop.name,
        }
    
    @staticmethod
    def refund_advance_payment(
        booking: Booking,
        reason: str = 'Booking cancelled'
    ) -> Dict[str, Any]:
        """
        Refund the advance payment for a cancelled booking.
        
        Args:
            booking: Booking to refund
            reason: Reason for refund
            
        Returns:
            Dictionary with success status
        """
        try:
            booking_payment = booking.advance_payment
        except BookingPayment.DoesNotExist:
            return {
                'success': True,
                'message': 'No payment to refund'
            }
        
        # Only refund if payment was actually made
        if booking_payment.status != BOOKING_PAYMENT_PAID:
            return {
                'success': True,
                'message': 'Payment was not completed, no refund needed'
            }
        
        # Process refund through Stripe
        refund = stripe_connect_client.refund_payment(
            payment_intent_id=booking_payment.stripe_payment_intent_id,
            reason='requested_by_customer'
        )
        
        if not refund:
            logger.error(f"Failed to refund payment for booking {booking.id}")
            return {
                'success': False,
                'error': 'Failed to process refund'
            }
        
        # Update payment record
        booking_payment.status = BOOKING_PAYMENT_REFUNDED
        booking_payment.refunded_at = timezone.now()
        booking_payment.stripe_refund_id = refund.id
        booking_payment.refund_reason = reason
        booking_payment.save(update_fields=[
            'status', 'refunded_at', 'stripe_refund_id', 'refund_reason'
        ])
        
        # Update booking
        booking.payment_status = BOOKING_PAYMENT_REFUNDED
        booking.save(update_fields=['payment_status'])
        
        logger.info(f"Refunded ${booking_payment.amount} for booking {booking.id}")
        
        return {
            'success': True,
            'refund_id': refund.id,
            'amount': booking_payment.amount,
        }


# Singleton instance
booking_payment_service = BookingPaymentService()
