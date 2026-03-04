"""
Twitter OAuth 2.0 (PKCE) login + JWT session management.

Flow:
  1. User visits /auth/twitter → redirect to Twitter authorize URL
  2. Twitter redirects to /auth/twitter/callback with ?code=...
  3. We exchange code for access token, fetch user info
  4. Create JWT session cookie → redirect back to report
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import urlencode

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# JWT settings
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 30 * 24 * 3600  # 30 days

# PKCE state store (in-memory, survives within a process lifetime)
_pending_auth: dict[str, dict] = {}


def _jwt_secret() -> str:
    """Use Stripe secret or a fallback as JWT signing key."""
    return settings.stripe_secret_key or settings.twitter_client_secret or "mckoutie-dev-secret"


def create_jwt(payload: dict) -> str:
    """Create a simple HMAC-SHA256 JWT."""
    header = urlsafe_b64encode(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload["exp"] = int(time.time()) + JWT_EXPIRY_SECONDS
    payload["iat"] = int(time.time())
    body = urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{body}"
    sig = hmac.new(_jwt_secret().encode(), signing_input.encode(), hashlib.sha256).digest()
    signature = urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header}.{body}.{signature}"


def verify_jwt(token: str) -> dict | None:
    """Verify and decode a JWT. Returns payload or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b, body_b, sig_b = parts
        signing_input = f"{header_b}.{body_b}"

        # Verify signature
        expected_sig = hmac.new(_jwt_secret().encode(), signing_input.encode(), hashlib.sha256).digest()
        # Pad base64
        sig_padded = sig_b + "=" * (4 - len(sig_b) % 4)
        actual_sig = urlsafe_b64decode(sig_padded)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        body_padded = body_b + "=" * (4 - len(body_b) % 4)
        payload = json.loads(urlsafe_b64decode(body_padded))

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


def get_twitter_auth_url(redirect_after: str = "/") -> tuple[str, str]:
    """
    Generate Twitter OAuth 2.0 authorization URL with PKCE.

    Returns (auth_url, state_token).
    """
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    # S256 code challenge
    code_challenge = (
        urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    # Store PKCE state
    _pending_auth[state] = {
        "code_verifier": code_verifier,
        "redirect_after": redirect_after,
        "created_at": time.time(),
    }

    # Clean old states (older than 10 min)
    cutoff = time.time() - 600
    for k in list(_pending_auth.keys()):
        if _pending_auth[k]["created_at"] < cutoff:
            del _pending_auth[k]

    callback_url = f"{settings.app_url}/auth/twitter/callback"

    params = {
        "response_type": "code",
        "client_id": settings.twitter_client_id,
        "redirect_uri": callback_url,
        "scope": "tweet.read users.read offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"
    return auth_url, state


async def exchange_code(code: str, state: str) -> dict | None:
    """
    Exchange authorization code for access token and fetch user info.

    Returns {"twitter_id": str, "username": str, "name": str} or None.
    """
    pending = _pending_auth.pop(state, None)
    if not pending:
        logger.error("Invalid or expired OAuth state")
        return None

    code_verifier = pending["code_verifier"]
    callback_url = f"{settings.app_url}/auth/twitter/callback"

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        try:
            token_resp = await client.post(
                "https://api.twitter.com/2/oauth2/token",
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": settings.twitter_client_id,
                    "redirect_uri": callback_url,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(settings.twitter_client_id, settings.twitter_client_secret),
                timeout=15,
            )

            if token_resp.status_code != 200:
                logger.error(f"Token exchange failed: {token_resp.status_code} {token_resp.text}")
                return None

            token_data = token_resp.json()
            access_token = token_data["access_token"]

            # Fetch user info
            user_resp = await client.get(
                "https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if user_resp.status_code != 200:
                logger.error(f"User info fetch failed: {user_resp.status_code}")
                return None

            user_data = user_resp.json().get("data", {})
            return {
                "twitter_id": user_data.get("id", ""),
                "username": user_data.get("username", ""),
                "name": user_data.get("name", ""),
                "redirect_after": pending.get("redirect_after", "/"),
            }

        except Exception as e:
            logger.error(f"OAuth exchange error: {e}")
            return None


def get_session_user(cookie_value: str | None) -> dict | None:
    """Extract user info from session cookie. Returns payload or None."""
    if not cookie_value:
        return None
    return verify_jwt(cookie_value)
