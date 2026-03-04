"""
Twitter mention polling — watches for @mckoutie mentions and parses requests.

Supported formats:
  @mckoutie analyse my startup https://example.com
  @mckoutie analyse my startup @somecompany
  @mckoutie analyze my startup example.com
  @mckoutie roast my startup https://example.com
"""

import re
import logging
import time
from dataclasses import dataclass

import tweepy

from src.config import settings

logger = logging.getLogger(__name__)

# Patterns to detect the request
TRIGGER_PATTERNS = [
    r"analy[sz]e\s+my\s+startup",
    r"roast\s+my\s+startup",
    r"review\s+my\s+startup",
    r"check\s+my\s+startup",
    r"consult\s+on",
]

# Extract URL or @username from tweet text
URL_PATTERN = re.compile(r"https?://[^\s]+|(?:www\.)[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?")
TWITTER_HANDLE_PATTERN = re.compile(r"@([a-zA-Z0-9_]{1,15})")


@dataclass
class AnalysisRequest:
    tweet_id: str
    author_id: str
    author_username: str
    text: str
    target_url: str | None = None
    target_twitter_handle: str | None = None
    created_at: str | None = None

    @property
    def has_target(self) -> bool:
        return bool(self.target_url or self.target_twitter_handle)

    @property
    def target_display(self) -> str:
        if self.target_url:
            return self.target_url
        if self.target_twitter_handle:
            return f"@{self.target_twitter_handle}"
        return "unknown"


class TwitterPoller:
    def __init__(self):
        self.client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            consumer_key=settings.twitter_api_key,
            consumer_secret=settings.twitter_api_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret,
            wait_on_rate_limit=True,
        )
        self.last_seen_id: str | None = None

    def _is_trigger(self, text: str) -> bool:
        """Check if tweet text contains a trigger phrase."""
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in TRIGGER_PATTERNS)

    def _extract_target(self, text: str) -> tuple[str | None, str | None]:
        """
        Extract either a URL or a Twitter handle from the tweet.
        Returns (url, handle) — one will be set, the other None.
        Ignores the bot's own @handle.
        """
        # Try URLs first (higher priority — more info to scrape)
        urls = URL_PATTERN.findall(text)
        for url in urls:
            # Skip twitter.com URLs that are just linking to the tweet itself
            if "twitter.com" in url or "x.com" in url:
                continue
            if not url.startswith("http"):
                url = "https://" + url
            return url, None

        # Fall back to @handles (excluding the bot itself)
        handles = TWITTER_HANDLE_PATTERN.findall(text)
        bot_username = settings.bot_username.lower()
        for handle in handles:
            if handle.lower() != bot_username:
                return None, handle

        return None, None

    def poll_mentions(self) -> list[AnalysisRequest]:
        """Poll for new mentions and return parsed analysis requests."""
        requests = []

        try:
            bot_id = self._get_bot_user_id()
            logger.info(f"Polling mentions for bot user ID: {bot_id} (since_id: {self.last_seen_id})")

            kwargs = {
                "expansions": ["author_id"],
                "tweet_fields": ["created_at", "text", "author_id"],
                "user_fields": ["username"],
                "max_results": 20,
            }
            if self.last_seen_id:
                kwargs["since_id"] = self.last_seen_id

            response = self.client.get_users_mentions(
                id=bot_id,
                **kwargs,
            )

            logger.info(f"Twitter API response: data={response.data is not None}, errors={getattr(response, 'errors', None)}")

            if not response.data:
                return []

            # Build user lookup from includes
            users = {}
            if response.includes and "users" in response.includes:
                for user in response.includes["users"]:
                    users[user.id] = user.username

            for tweet in response.data:
                # Update high-water mark
                if not self.last_seen_id or int(tweet.id) > int(self.last_seen_id):
                    self.last_seen_id = str(tweet.id)

                logger.info(f"Mention received [{tweet.id}]: {tweet.text[:200]}")

                if not self._is_trigger(tweet.text):
                    logger.info(f"Skipping non-trigger tweet: {tweet.id}")
                    continue

                url, handle = self._extract_target(tweet.text)

                req = AnalysisRequest(
                    tweet_id=str(tweet.id),
                    author_id=str(tweet.author_id),
                    author_username=users.get(tweet.author_id, "unknown"),
                    text=tweet.text,
                    target_url=url,
                    target_twitter_handle=handle,
                    created_at=str(tweet.created_at) if tweet.created_at else None,
                )

                if req.has_target:
                    requests.append(req)
                    logger.info(f"New request from @{req.author_username}: {req.target_display}")
                else:
                    logger.warning(
                        f"Trigger found but no target in tweet {tweet.id} from @{users.get(tweet.author_id, '?')}"
                    )

        except tweepy.TooManyRequests:
            logger.warning("Rate limited — backing off 60s")
            time.sleep(60)
        except tweepy.Forbidden as e:
            logger.error(
                f"Twitter 403 Forbidden: {e}. "
                "Mention timeline requires Basic tier ($100/mo) or higher. "
                "Free tier only allows tweet creation, not reading mentions."
            )
        except tweepy.Unauthorized as e:
            logger.error(f"Twitter 401 Unauthorized: {e}. Check your API keys are correct.")
        except tweepy.TwitterServerError as e:
            logger.error(f"Twitter server error: {e}")
        except Exception as e:
            logger.error(f"Error polling mentions: {e}")

        return requests

    def _get_bot_user_id(self) -> str:
        """Get the authenticated user's ID (cached after first call)."""
        if not hasattr(self, "_bot_user_id"):
            me = self.client.get_me()
            self._bot_user_id = str(me.data.id)
        return self._bot_user_id

    def reply_to_tweet(self, tweet_id: str, text: str) -> str | None:
        """Reply to a tweet. Returns the reply tweet ID or None on failure."""
        try:
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=tweet_id,
            )
            return str(response.data["id"])
        except Exception as e:
            logger.error(f"Failed to reply to {tweet_id}: {e}")
            return None

    def reply_thread(self, tweet_id: str, texts: list[str]) -> list[str]:
        """Reply with a thread of tweets. Returns list of reply IDs."""
        reply_ids = []
        parent_id = tweet_id

        for text in texts:
            reply_id = self.reply_to_tweet(parent_id, text)
            if reply_id:
                reply_ids.append(reply_id)
                parent_id = reply_id
            else:
                break

        return reply_ids

    def send_dm(self, user_id: str, text: str) -> bool:
        """Send a DM to a user."""
        try:
            self.client.create_direct_message(
                participant_id=user_id,
                text=text,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to DM user {user_id}: {e}")
            return False
