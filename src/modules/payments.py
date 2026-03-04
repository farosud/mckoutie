"""
Stripe subscription module — creates checkout sessions for tiered subscriptions.

Tiers:
  - Starter: $39/mo  — startup strategy brief with market intelligence
  - Growth:  $200/mo — full strategy brief with lead discovery, investor research

Flow:
  1. Analysis completes → create_checkout_session(report_id, tier="starter"|"growth")
  2. Returns a Stripe checkout URL (subscription mode)
  3. User subscribes → Stripe webhook → mark report as active → unlock access
  4. Monthly renewals keep access alive
  5. Subscription canceled → access revoked
  6. create_upgrade_session() lets existing starter users upgrade to growth
"""

import logging

import stripe

from src.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# Cache price IDs so we only create them once
_cached_price_id: str | None = None
_cached_growth_price_id: str | None = None


def _get_or_create_price() -> str:
    """Get existing price ID or create a recurring $39/mo price."""
    global _cached_price_id

    if settings.stripe_price_id:
        return settings.stripe_price_id

    if _cached_price_id:
        return _cached_price_id

    try:
        # Search for existing mckoutie product
        products = stripe.Product.search(query='name~"mckoutie"', limit=1)
        if products.data:
            product = products.data[0]
            # Find recurring price
            prices = stripe.Price.list(product=product.id, type="recurring", active=True, limit=1)
            if prices.data:
                _cached_price_id = prices.data[0].id
                logger.info(f"Using existing price: {_cached_price_id}")
                return _cached_price_id

        # Create product + price
        product = stripe.Product.create(
            name="mckoutie Market Intelligence",
            description="Monthly startup strategy brief with ongoing market intelligence updates.",
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=settings.report_price_usd * 100,
            currency="usd",
            recurring={"interval": "month"},
        )
        _cached_price_id = price.id
        logger.info(f"Created new price: {_cached_price_id}")
        return _cached_price_id

    except Exception as e:
        logger.error(f"Failed to get/create price: {e}")
        raise


def _get_or_create_growth_price() -> str:
    """Get existing growth price ID or create a recurring $200/mo price."""
    global _cached_growth_price_id

    if settings.stripe_growth_price_id:
        return settings.stripe_growth_price_id

    if _cached_growth_price_id:
        return _cached_growth_price_id

    try:
        # Search for existing growth product
        products = stripe.Product.search(
            query='name~"mckoutie Growth Intelligence"', limit=1
        )
        if products.data:
            product = products.data[0]
            # Find recurring price
            prices = stripe.Price.list(
                product=product.id, type="recurring", active=True, limit=1
            )
            if prices.data:
                _cached_growth_price_id = prices.data[0].id
                logger.info(f"Using existing growth price: {_cached_growth_price_id}")
                return _cached_growth_price_id

        # Create product + price
        product = stripe.Product.create(
            name="mckoutie Growth Intelligence",
            description=(
                "Full startup strategy brief with lead discovery, "
                "investor research, and ongoing market intelligence."
            ),
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=settings.growth_price_usd * 100,
            currency="usd",
            recurring={"interval": "month"},
        )
        _cached_growth_price_id = price.id
        logger.info(f"Created new growth price: {_cached_growth_price_id}")
        return _cached_growth_price_id

    except Exception as e:
        logger.error(f"Failed to get/create growth price: {e}")
        raise


def create_checkout_session(
    report_id: str,
    startup_name: str,
    tweet_author: str,
    twitter_id: str = "",
    tier: str = "starter",
) -> str | None:
    """
    Create a Stripe Checkout session for a monthly subscription.

    Args:
        tier: "starter" ($39/mo) or "growth" ($200/mo).

    Returns the checkout URL, or None on failure.
    """
    try:
        if tier == "growth":
            price_id = _get_or_create_growth_price()
        else:
            price_id = _get_or_create_price()

        metadata = {
            "report_id": report_id,
            "startup_name": startup_name,
            "tweet_author": tweet_author,
            "twitter_id": twitter_id,
            "tier": tier,
        }

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.app_url}/report/{report_id}?paid=true",
            cancel_url=f"{settings.app_url}/report/{report_id}?paid=false",
            metadata=metadata,
            subscription_data={"metadata": metadata},
        )
        logger.info(
            f"{tier.capitalize()} checkout created for report {report_id}: {session.url}"
        )
        return session.url
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        return None


def create_upgrade_session(
    report_id: str,
    startup_name: str,
    customer_id: str = "",
) -> str | None:
    """
    Create a Stripe Checkout session for upgrading from starter to growth tier.

    If a customer_id is provided, it will be attached to the session so Stripe
    links the new subscription to the existing customer.

    Returns the checkout URL, or None on failure.
    """
    try:
        price_id = _get_or_create_growth_price()

        metadata = {
            "report_id": report_id,
            "startup_name": startup_name,
            "tier": "growth",
            "upgrade_from": "starter",
        }

        session_params: dict = {
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "mode": "subscription",
            "success_url": f"{settings.app_url}/report/{report_id}?upgraded=true",
            "cancel_url": f"{settings.app_url}/report/{report_id}?upgraded=false",
            "metadata": metadata,
            "subscription_data": {"metadata": metadata},
        }

        if customer_id:
            session_params["customer"] = customer_id

        session = stripe.checkout.Session.create(**session_params)
        logger.info(
            f"Upgrade checkout created for report {report_id}: {session.url}"
        )
        return session.url
    except Exception as e:
        logger.error(f"Failed to create upgrade session: {e}")
        return None


def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a subscription."""
    try:
        stripe.Subscription.cancel(subscription_id)
        logger.info(f"Subscription {subscription_id} canceled")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        return False


def get_subscription_status(subscription_id: str) -> str | None:
    """Get current subscription status."""
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        return sub.status  # active, past_due, canceled, unpaid
    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
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
