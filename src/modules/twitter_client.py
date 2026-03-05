"""
Raw OAuth 1.0a Twitter API client.

Tweepy's OAuth handling is broken on the X API pay-per-use tier.
This module implements OAuth 1.0a signing manually with httpx,
which works correctly with the new pricing model.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twitter.com"
UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


@dataclass
class TwitterCredentials:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str


class TwitterClient:
    """Lightweight Twitter API v2 client using raw OAuth 1.0a."""

    def __init__(self, creds: TwitterCredentials):
        self.creds = creds
        self._http = httpx.Client(timeout=30.0)
        self._user_id: str | None = None
        self._username: str | None = None

    def _sign_request(
        self, method: str, url: str, params: dict | None = None
    ) -> dict[str, str]:
        """Build OAuth 1.0a Authorization header."""
        oauth_params = {
            "oauth_consumer_key": self.creds.api_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.creds.access_token,
            "oauth_version": "1.0",
        }

        # Combine oauth params + query params for signature base
        all_params = {**oauth_params}
        if params:
            all_params.update({k: str(v) for k, v in params.items()})

        # Sort and encode
        sorted_encoded = "&".join(
            f"{urllib.parse.quote(k, safe='')}"
            f"={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(all_params.items())
        )

        base_string = (
            f"{method.upper()}"
            f"&{urllib.parse.quote(url, safe='')}"
            f"&{urllib.parse.quote(sorted_encoded, safe='')}"
        )

        signing_key = (
            f"{urllib.parse.quote(self.creds.api_secret, safe='')}"
            f"&{urllib.parse.quote(self.creds.access_token_secret, safe='')}"
        )

        signature = base64.b64encode(
            hmac.new(
                signing_key.encode(), base_string.encode(), hashlib.sha1
            ).digest()
        ).decode()

        oauth_params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{k}="{urllib.parse.quote(str(v), safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        return {"Authorization": auth_header}

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        url = f"{BASE_URL}{path}"
        headers = self._sign_request("GET", url, params)
        query = (
            "&".join(
                f"{k}={urllib.parse.quote(str(v), safe='')}"
                for k, v in params.items()
            )
            if params
            else ""
        )
        full_url = f"{url}?{query}" if query else url
        return self._http.get(full_url, headers=headers)

    def _post(
        self, path: str, json_body: dict | None = None
    ) -> httpx.Response:
        url = f"{BASE_URL}{path}"
        headers = self._sign_request("POST", url)
        headers["Content-Type"] = "application/json"
        return self._http.post(url, headers=headers, json=json_body or {})

    # --- Public API methods ---

    def get_me(self) -> dict:
        """GET /2/users/me — returns {id, name, username}."""
        r = self._get("/2/users/me")
        r.raise_for_status()
        data = r.json().get("data", {})
        self._user_id = data.get("id")
        self._username = data.get("username")
        return data

    @property
    def user_id(self) -> str:
        if not self._user_id:
            self.get_me()
        return self._user_id

    @property
    def username(self) -> str:
        if not self._username:
            self.get_me()
        return self._username

    def get_mentions(
        self,
        since_id: str | None = None,
        max_results: int = 20,
    ) -> dict:
        """
        GET /2/users/:id/mentions
        Returns {data: [...tweets], meta: {newest_id, oldest_id, ...}}.
        """
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,text,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }
        if since_id:
            params["since_id"] = since_id

        r = self._get(f"/2/users/{self.user_id}/mentions", params)

        if r.status_code == 429:
            reset = r.headers.get("x-rate-limit-reset", "")
            logger.warning(f"Rate limited on mentions. Reset: {reset}")
            return {"rate_limited": True}

        if r.status_code != 200:
            logger.error(
                f"Mentions API error {r.status_code}: {r.text[:300]}"
            )
            return {"error": r.status_code, "detail": r.text[:300]}

        return r.json()

    def upload_media(self, file_path: str | Path) -> str | None:
        """
        Upload media via Twitter v1.1 media/upload (simple upload).
        Returns media_id_string on success, None on failure.

        Supports images up to 5MB (JPEG, PNG, GIF, WEBP).
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Media file not found: {path}")
            return None

        file_size = path.stat().st_size
        if file_size > 5 * 1024 * 1024:
            logger.error(f"Media file too large: {file_size} bytes (max 5MB)")
            return None

        # Read file content
        media_data = path.read_bytes()

        # Determine media type
        suffix = path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/png")

        # OAuth sign against the upload URL (no query params for multipart)
        headers = self._sign_request("POST", UPLOAD_URL)
        # Do NOT set Content-Type — httpx sets it with boundary for multipart

        try:
            r = self._http.post(
                UPLOAD_URL,
                headers=headers,
                files={"media_data": (path.name, media_data, media_type)},
            )

            if r.status_code not in (200, 201, 202):
                logger.error(f"Media upload failed {r.status_code}: {r.text[:300]}")
                return None

            media_id = r.json().get("media_id_string")
            logger.info(f"Media uploaded: {media_id} ({file_size} bytes)")
            return media_id

        except Exception as e:
            logger.error(f"Media upload error: {e}")
            return None

    def create_tweet(
        self,
        text: str,
        reply_to: str | None = None,
        media_ids: list[str] | None = None,
    ) -> dict | None:
        """
        POST /2/tweets — create a tweet, optionally as a reply with media.
        Returns {id, text} or None on failure.
        """
        body: dict = {"text": text}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        if media_ids:
            body["media"] = {"media_ids": media_ids}

        r = self._post("/2/tweets", body)

        if r.status_code not in (200, 201):
            logger.error(f"Create tweet failed {r.status_code}: {r.text[:300]}")
            return None

        return r.json().get("data")

    def reply_thread(self, tweet_id: str, texts: list[str]) -> list[str]:
        """Post a thread of replies with anti-spam delays between tweets."""
        import random as _random

        reply_ids = []
        parent_id = tweet_id

        for i, text in enumerate(texts):
            # Add jittered delay between tweets (3-6s) to avoid machine-gun posting
            if i > 0:
                delay = 3.0 + _random.random() * 3.0
                logger.debug(f"Thread anti-spam delay: {delay:.1f}s before tweet {i + 1}")
                time.sleep(delay)

            result = self.create_tweet(text, reply_to=parent_id)
            if result:
                reply_ids.append(result["id"])
                parent_id = result["id"]
            else:
                logger.error(f"Thread broken at tweet {len(reply_ids) + 1}")
                break

        return reply_ids

    def get_user_by_username(self, username: str) -> dict | None:
        """GET /2/users/by/username/:username — lookup a user."""
        params = {
            "user.fields": "description,public_metrics,url,location,verified",
        }
        r = self._get(f"/2/users/by/username/{username}", params)
        if r.status_code != 200:
            logger.error(f"User lookup failed: {r.status_code}")
            return None
        return r.json().get("data")

    def get_user_tweets(
        self, user_id: str, max_results: int = 10
    ) -> list[dict]:
        """GET /2/users/:id/tweets — get recent tweets from a user."""
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,text,public_metrics",
        }
        r = self._get(f"/2/users/{user_id}/tweets", params)
        if r.status_code != 200:
            return []
        return r.json().get("data", [])

    def close(self):
        self._http.close()
