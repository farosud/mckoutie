"""
Supabase database layer for mckoutie.

Tables: users, reports, subscriptions.
Falls back gracefully to file-based storage if Supabase is not configured.
"""

import logging
from datetime import datetime, timezone

from src.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """Lazy-initialize the Supabase client."""
    global _client
    if _client is not None:
        return _client
    if not settings.has_supabase:
        return None
    try:
        from supabase import create_client
        _client = create_client(settings.supabase_url, settings.supabase_key)
        logger.info("Supabase client initialized")
        return _client
    except Exception as e:
        logger.error(f"Failed to init Supabase: {e}")
        return None


# ── Users ──────────────────────────────────────────────────────────────

def upsert_user(twitter_id: str, username: str, name: str) -> dict | None:
    """Create or update a user on login. Returns the user row."""
    client = get_client()
    if not client:
        return None
    try:
        now = datetime.now(tz=timezone.utc).isoformat()
        data = {
            "twitter_id": twitter_id,
            "username": username,
            "name": name,
            "updated_at": now,
        }
        result = (
            client.table("users")
            .upsert(data, on_conflict="twitter_id")
            .execute()
        )
        if result.data:
            logger.info(f"Upserted user @{username} (twitter_id={twitter_id})")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to upsert user: {e}")
        return None


def get_user_by_twitter_id(twitter_id: str) -> dict | None:
    """Fetch user by Twitter ID."""
    client = get_client()
    if not client:
        return None
    try:
        result = (
            client.table("users")
            .select("*")
            .eq("twitter_id", twitter_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get user: {e}")
        return None


def update_user_stripe(twitter_id: str, stripe_customer_id: str) -> None:
    """Link a Stripe customer ID to a user."""
    client = get_client()
    if not client:
        return
    try:
        client.table("users").update(
            {"stripe_customer_id": stripe_customer_id}
        ).eq("twitter_id", twitter_id).execute()
    except Exception as e:
        logger.error(f"Failed to update user Stripe ID: {e}")


# ── Reports ────────────────────────────────────────────────────────────

def create_report(
    report_id: str,
    startup_name: str,
    target: str,
    tweet_id: str,
    author_twitter_id: str,
    author_username: str,
) -> dict | None:
    """Insert a new report record."""
    client = get_client()
    if not client:
        return None
    try:
        # Find owner_id from users table
        user = get_user_by_twitter_id(author_twitter_id)
        owner_id = user["id"] if user else None

        data = {
            "report_id": report_id,
            "startup_name": startup_name,
            "target": target,
            "tweet_id": tweet_id,
            "author_twitter_id": author_twitter_id,
            "author_username": author_username,
            "status": "pending",
            "owner_id": owner_id,
        }
        result = client.table("reports").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to create report: {e}")
        return None


def get_report(report_id: str) -> dict | None:
    """Fetch a report by its short ID."""
    client = get_client()
    if not client:
        return None
    try:
        result = (
            client.table("reports")
            .select("*")
            .eq("report_id", report_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        return None


def update_report(report_id: str, **kwargs) -> dict | None:
    """Update fields on a report."""
    client = get_client()
    if not client:
        return None
    try:
        result = (
            client.table("reports")
            .update(kwargs)
            .eq("report_id", report_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to update report: {e}")
        return None


def get_reports_by_twitter_id(twitter_id: str) -> list[dict]:
    """Get all reports owned by a Twitter user."""
    client = get_client()
    if not client:
        return []
    try:
        result = (
            client.table("reports")
            .select("*")
            .eq("author_twitter_id", twitter_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get reports by user: {e}")
        return []


def get_active_subscribed_reports() -> list[dict]:
    """Get all reports with active status for market updates."""
    client = get_client()
    if not client:
        return []
    try:
        result = (
            client.table("reports")
            .select("*")
            .eq("status", "active")
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get active reports: {e}")
        return []


# ── Subscriptions ──────────────────────────────────────────────────────

def create_subscription(
    twitter_id: str,
    report_id: str,
    stripe_subscription_id: str,
    stripe_customer_id: str,
    tier: str = "starter",
) -> dict | None:
    """Create a subscription record after Stripe checkout."""
    client = get_client()
    if not client:
        return None
    try:
        user = get_user_by_twitter_id(twitter_id)
        if not user:
            logger.error(f"No user found for twitter_id={twitter_id}")
            return None

        data = {
            "user_id": user["id"],
            "report_id": report_id,
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": stripe_customer_id,
            "tier": tier,
            "status": "active",
        }
        result = client.table("subscriptions").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        return None


def cancel_subscription_by_stripe_id(stripe_subscription_id: str) -> bool:
    """Mark a subscription as canceled."""
    client = get_client()
    if not client:
        return False
    try:
        now = datetime.now(tz=timezone.utc).isoformat()
        client.table("subscriptions").update(
            {"status": "canceled", "canceled_at": now}
        ).eq("stripe_subscription_id", stripe_subscription_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        return False


def get_subscription_for_report(report_id: str, twitter_id: str) -> dict | None:
    """Get active subscription for a specific report and user."""
    client = get_client()
    if not client:
        return None
    try:
        user = get_user_by_twitter_id(twitter_id)
        if not user:
            return None
        result = (
            client.table("subscriptions")
            .select("*")
            .eq("report_id", report_id)
            .eq("user_id", user["id"])
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
        return None
