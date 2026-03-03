"""
Stripe payment module — creates checkout sessions and handles webhooks.

Flow:
  1. Analysis completes → create_checkout_session(report_id)
  2. Returns a Stripe checkout URL
  3. User pays → Stripe webhook → mark report as paid → unlock access
"""

import logging

import stripe

from src.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key


def create_checkout_session(
    report_id: str,
    startup_name: str,
    tweet_author: str,
) -> str | None:
    """
    Create a Stripe Checkout session for a report.

    Returns the checkout URL, or None on failure.
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"mckoutie Strategy Brief: {startup_name}",
                            "description": (
                                f"Full 19-channel traction analysis, 90-day plan, "
                                f"budget allocation, and risk matrix for {startup_name}."
                            ),
                        },
                        "unit_amount": settings.report_price_usd * 100,  # cents
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{settings.app_url}/report/{report_id}?paid=true",
            cancel_url=f"{settings.app_url}/report/{report_id}?paid=false",
            metadata={
                "report_id": report_id,
                "startup_name": startup_name,
                "tweet_author": tweet_author,
            },
        )
        logger.info(f"Checkout session created for report {report_id}: {session.url}")
        return session.url
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        return None


def verify_webhook(payload: bytes, sig_header: str) -> dict | None:
    """
    Verify and parse a Stripe webhook event.
    Returns the event dict or None if verification fails.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
        return event
    except stripe.SignatureVerificationError:
        logger.error("Stripe webhook signature verification failed")
        return None
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return None
