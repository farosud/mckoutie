"""
Twitter profile analyzer — when someone tags a @handle instead of a URL,
we analyze their Twitter presence to understand the startup.
"""

import logging

import tweepy

from src.config import settings

logger = logging.getLogger(__name__)


async def analyze_twitter_profile(handle: str) -> dict:
    """
    Analyze a Twitter/X profile to extract startup intelligence.

    Returns:
        {
            "handle": str,
            "name": str,
            "bio": str,
            "followers": int,
            "following": int,
            "tweet_count": int,
            "website": str | None,
            "recent_tweets": list[str],
            "pinned_tweet": str | None,
            "topics": list[str],           # inferred from tweets
            "profile_summary": str,        # compiled intelligence
        }
    """
    client = tweepy.Client(
        bearer_token=settings.twitter_bearer_token,
        wait_on_rate_limit=True,
    )

    # Get user profile
    try:
        user_resp = client.get_user(
            username=handle,
            user_fields=[
                "description",
                "public_metrics",
                "url",
                "pinned_tweet_id",
                "created_at",
                "location",
            ],
            expansions=["pinned_tweet_id"],
            tweet_fields=["text"],
        )
    except Exception as e:
        logger.error(f"Failed to fetch profile for @{handle}: {e}")
        return _empty_profile(handle)

    if not user_resp.data:
        return _empty_profile(handle)

    user = user_resp.data
    metrics = user.public_metrics or {}

    # Extract pinned tweet
    pinned_tweet = None
    if user_resp.includes and "tweets" in user_resp.includes:
        pinned_tweet = user_resp.includes["tweets"][0].text

    # Get recent tweets
    recent_tweets = []
    try:
        tweets_resp = client.get_users_tweets(
            id=user.id,
            max_results=20,
            tweet_fields=["text", "public_metrics", "created_at"],
            exclude=["retweets"],
        )
        if tweets_resp.data:
            recent_tweets = [t.text for t in tweets_resp.data]
    except Exception as e:
        logger.warning(f"Failed to fetch tweets for @{handle}: {e}")

    # Compile the profile
    website = None
    if user.url:
        website = user.url
    elif user.entities and "url" in user.entities:
        urls = user.entities["url"].get("urls", [])
        if urls:
            website = urls[0].get("expanded_url", urls[0].get("url"))

    profile = {
        "handle": handle,
        "name": user.name or handle,
        "bio": user.description or "",
        "followers": metrics.get("followers_count", 0),
        "following": metrics.get("following_count", 0),
        "tweet_count": metrics.get("tweet_count", 0),
        "website": website,
        "location": getattr(user, "location", None),
        "created_at": str(user.created_at) if user.created_at else None,
        "recent_tweets": recent_tweets,
        "pinned_tweet": pinned_tweet,
        "profile_summary": _compile_summary(user, metrics, recent_tweets, pinned_tweet),
    }

    return profile


def _compile_summary(user, metrics: dict, tweets: list[str], pinned: str | None) -> str:
    """Compile all profile data into a text summary for the LLM."""
    parts = [
        f"Twitter Profile: @{user.username}",
        f"Name: {user.name}",
        f"Bio: {user.description or 'No bio'}",
        f"Followers: {metrics.get('followers_count', 0):,}",
        f"Following: {metrics.get('following_count', 0):,}",
        f"Tweets: {metrics.get('tweet_count', 0):,}",
    ]

    if hasattr(user, "location") and user.location:
        parts.append(f"Location: {user.location}")

    if pinned:
        parts.append(f"\nPinned Tweet:\n{pinned}")

    if tweets:
        parts.append(f"\nRecent Tweets ({len(tweets)}):")
        for i, tweet in enumerate(tweets[:15], 1):
            # Truncate long tweets
            display = tweet[:280] + "..." if len(tweet) > 280 else tweet
            parts.append(f"  {i}. {display}")

    return "\n".join(parts)


def _empty_profile(handle: str) -> dict:
    return {
        "handle": handle,
        "name": handle,
        "bio": "",
        "followers": 0,
        "following": 0,
        "tweet_count": 0,
        "website": None,
        "location": None,
        "created_at": None,
        "recent_tweets": [],
        "pinned_tweet": None,
        "profile_summary": f"Could not fetch profile for @{handle}",
    }
