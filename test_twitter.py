"""Quick test: verify Twitter API credentials work."""
import os
import sys
from urllib.parse import unquote

# Load .env manually
from pathlib import Path
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

import tweepy

bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
api_key = os.getenv("TWITTER_API_KEY", "")
api_secret = os.getenv("TWITTER_API_SECRET", "")
access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

# URL-decode bearer if needed
if "%2" in bearer or "%3" in bearer:
    bearer = unquote(bearer)
    print(f"[info] Bearer token was URL-encoded, decoded it")

print(f"[info] Bearer token: {bearer[:30]}...{bearer[-10:]}")
print(f"[info] API Key: {api_key[:8]}...")
print(f"[info] Access Token: {access_token[:15]}...")

# Test 1: Bearer-only client (app-level auth)
print("\n--- Test 1: App auth (bearer only) ---")
try:
    app_client = tweepy.Client(bearer_token=bearer)
    me_lookup = app_client.get_user(username="mckoutie")
    if me_lookup.data:
        print(f"  OK: Found @mckoutie (id={me_lookup.data.id})")
        bot_id = me_lookup.data.id
    else:
        print(f"  FAIL: No data returned")
        bot_id = None
except Exception as e:
    print(f"  FAIL: {e}")
    bot_id = None

# Test 2: User auth (OAuth 1.0a) - needed for mentions + posting
print("\n--- Test 2: User auth (OAuth 1.0a) ---")
try:
    user_client = tweepy.Client(
        bearer_token=bearer,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    me = user_client.get_me()
    if me.data:
        print(f"  OK: Authenticated as @{me.data.username} (id={me.data.id})")
    else:
        print(f"  FAIL: get_me() returned no data")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 3: Read mentions (the actual endpoint the bot uses)
print("\n--- Test 3: Read mentions ---")
# Use the bot ID from OAuth auth (Test 2) if bearer failed
try:
    if not bot_id:
        me2 = user_client.get_me()
        bot_id = me2.data.id if me2.data else None
        print(f"  Got bot_id from OAuth: {bot_id}")
except:
    pass

if bot_id:
    try:
        mentions = user_client.get_users_mentions(
            id=bot_id,
            max_results=5,
            tweet_fields=["created_at", "text", "author_id"],
        )
        if mentions.data:
            print(f"  OK: Found {len(mentions.data)} mention(s)")
            for t in mentions.data[:3]:
                print(f"    [{t.id}] {t.text[:100]}")
        elif mentions.errors:
            print(f"  ERRORS: {mentions.errors}")
        else:
            print(f"  OK: No mentions yet (empty inbox)")
    except tweepy.Unauthorized as e:
        print(f"  FAIL (401): {e}")
        print("  → OAuth keys can't read mentions")
    except tweepy.Forbidden as e:
        print(f"  FAIL (403): {e}")
        print("  → Need pay-per-use credits or Read+Write permissions")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
else:
    print("  SKIP: Could not get bot_id")

# Test 4: Can we post? (dry run - don't actually tweet)
print("\n--- Test 4: Post capability (dry check) ---")
try:
    # Just verify OAuth is set up for write - don't actually post
    if all([api_key, api_secret, access_token, access_secret]):
        print(f"  OK: All OAuth credentials present for posting")
    else:
        missing = []
        if not api_key: missing.append("API_KEY")
        if not api_secret: missing.append("API_SECRET")
        if not access_token: missing.append("ACCESS_TOKEN")
        if not access_secret: missing.append("ACCESS_TOKEN_SECRET")
        print(f"  WARN: Missing: {', '.join(missing)}")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n--- Done ---")
