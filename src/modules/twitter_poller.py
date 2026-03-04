"""
Twitter mention polling — watches for @mckoutie mentions and parses requests.

Supported formats:
  @mckoutie analyse my startup https://example.com
  @mckoutie analyse my startup @somecompany
  @mckoutie analyze my startup example.com
  @mckoutie roast my startup https://example.com
"""

import json
import os
import re
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.config import settings
from src.modules.twitter_client import TwitterClient, TwitterCredentials

logger = logging.getLogger(__name__)

# Persistent state file for surviving restarts/deploys
STATE_FILE = Path(os.getenv("STATE_DIR", "/tmp")) / "mckoutie_poller_state.json"

# Patterns to detect the request — intentionally permissive.
# If someone tags @mckoutie with anything resembling a request, process it.
TRIGGER_PATTERNS = [
    r"analy[sz]e\b",          # "analyze", "analyse" anywhere in the tweet
    r"roast\b",               # "roast" anywhere
    r"review\b",              # "review" anywhere
    r"check\s+(my|this|it|out)",  # "check my/this/it out"
    r"consult\b",             # "consult" anywhere
    r"https?://",             # any mention containing a non-twitter URL (checked in _is_trigger)
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
        creds = TwitterCredentials(
            api_key=settings.twitter_api_key,
            api_secret=settings.twitter_api_secret,
            access_token=settings.twitter_access_token,
            access_token_secret=settings.twitter_access_token_secret,
        )
        self.client = TwitterClient(creds)
        self.last_seen_id: str | None = self._load_state()

    def _load_state(self) -> str | None:
        """Load last_seen_id from disk to survive restarts."""
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                last_id = data.get("last_seen_id")
                if last_id:
                    logger.info(f"Restored last_seen_id from disk: {last_id}")
                return last_id
        except Exception as e:
            logger.warning(f"Failed to load poller state: {e}")
        return None

    def _save_state(self):
        """Persist last_seen_id to disk."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"last_seen_id": self.last_seen_id}))
        except Exception as e:
            logger.warning(f"Failed to save poller state: {e}")

    def _is_trigger(self, text: str) -> bool:
        """Check if tweet text contains a trigger phrase.

        Very permissive — if someone mentions @mckoutie with any action word
        or a URL, we treat it as a request. Better to process a false positive
        than miss a real request.
        """
        text_lower = text.lower()
        for pattern in TRIGGER_PATTERNS:
            if pattern == r"https?://":
                # For bare URL pattern, only trigger if there's a non-Twitter URL
                urls = re.findall(r"https?://[^\s]+", text_lower)
                if any(u for u in urls if "twitter.com" not in u and "x.com" not in u and "t.co" not in u):
                    return True
            elif re.search(pattern, text_lower):
                return True
        return False

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
            logger.info(
                f"Polling mentions for @{self.client.username} "
                f"(since_id: {self.last_seen_id})"
            )

            response = self.client.get_mentions(
                since_id=self.last_seen_id,
                max_results=20,
            )

            # Handle errors
            if response.get("rate_limited"):
                logger.warning("Rate limited — will retry next cycle")
                return []

            if response.get("error"):
                logger.error(
                    f"Mentions API returned {response['error']}: "
                    f"{response.get('detail', '')}"
                )
                return []

            tweets = response.get("data", [])
            if not tweets:
                return []

            logger.info(f"Got {len(tweets)} mention(s)")

            # Build user lookup from includes
            users = {}
            includes = response.get("includes", {})
            for user in includes.get("users", []):
                users[user["id"]] = user["username"]

            for tweet in tweets:
                tweet_id = tweet["id"]
                author_id = tweet.get("author_id", "")
                text = tweet.get("text", "")

                # Update high-water mark
                if not self.last_seen_id or int(tweet_id) > int(self.last_seen_id):
                    self.last_seen_id = str(tweet_id)

                logger.info(f"Mention [{tweet_id}]: {text[:200]}")

                if not self._is_trigger(text):
                    logger.info(f"Skipping non-trigger tweet: {tweet_id}")
                    continue

                url, handle = self._extract_target(text)

                req = AnalysisRequest(
                    tweet_id=str(tweet_id),
                    author_id=str(author_id),
                    author_username=users.get(author_id, "unknown"),
                    text=text,
                    target_url=url,
                    target_twitter_handle=handle,
                    created_at=tweet.get("created_at"),
                )

                if req.has_target:
                    requests.append(req)
                    logger.info(
                        f"New request from @{req.author_username}: "
                        f"{req.target_display}"
                    )
                else:
                    logger.warning(
                        f"Trigger found but no target in tweet {tweet_id} "
                        f"from @{users.get(author_id, '?')}"
                    )

            # Persist state after successful poll
            if self.last_seen_id:
                self._save_state()

        except Exception as e:
            logger.error(f"Error polling mentions: {e}")

        return requests

    def reply_to_tweet(
        self, tweet_id: str, text: str, media_ids: list[str] | None = None
    ) -> str | None:
        """Reply to a tweet, optionally with media. Returns the reply tweet ID or None."""
        result = self.client.create_tweet(text, reply_to=tweet_id, media_ids=media_ids)
        if result:
            return result["id"]
        return None

    def upload_media(self, file_path: str) -> str | None:
        """Upload media and return media_id_string."""
        return self.client.upload_media(file_path)

    def reply_thread(self, tweet_id: str, texts: list[str]) -> list[str]:
        """Reply with a thread of tweets. Returns list of reply IDs."""
        return self.client.reply_thread(tweet_id, texts)

    def send_dm(self, user_id: str, text: str) -> bool:
        """Send a DM to a user. Not yet implemented for raw client."""
        logger.warning("DMs not yet implemented in raw OAuth client")
        return False
