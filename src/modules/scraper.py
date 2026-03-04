"""
Website scraping module — extracts startup info from websites.

Cascade: Firecrawl → Exa → Jina Reader → raw httpx fallback.
"""

import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def resolve_url(url: str) -> str:
    """
    Follow redirects to resolve shortened URLs (t.co, bit.ly, etc.)
    to their final destination. Returns the resolved URL.
    """
    if not url.startswith("http"):
        url = "https://" + url

    # Check if this looks like a shortened URL that needs resolving
    short_domains = ["t.co", "bit.ly", "goo.gl", "ow.ly", "tinyurl.com", "is.gd", "buff.ly"]
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if not any(hostname == d or hostname.endswith(f".{d}") for d in short_domains):
        return url  # Not a short URL, no need to resolve

    logger.info(f"Resolving shortened URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    # Try GET first (more reliable than HEAD for URL shorteners)
    for method in ["GET", "HEAD"]:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, max_redirects=10) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.head(url, headers=headers)
                resolved = str(resp.url)
                if resolved != url:
                    logger.info(f"Resolved {url} -> {resolved} (via {method})")
                    return resolved
                logger.info(f"{method} returned same URL: {url}")
                return resolved
        except Exception as e:
            logger.warning(f"URL resolve {method} failed for {url}: {e}")
            continue

    logger.warning(f"All resolve methods failed for {url}, returning original")
    return url


async def scrape_website(url: str) -> dict:
    """
    Scrape a startup website and return structured content.

    Returns:
        {
            "url": str,
            "title": str,
            "description": str,
            "content": str,      # full page text as markdown
            "links": list[str],  # important links found
            "source": str,       # which scraper succeeded
        }
    """
    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url

    # Resolve shortened URLs (t.co, bit.ly, etc.) before scraping
    url = await resolve_url(url)

    # Try each direct scraper in order
    for scraper_fn in [_scrape_firecrawl, _scrape_exa, _scrape_jina, _scrape_raw]:
        try:
            result = await scraper_fn(url)
            if result and result.get("content") and len(result["content"]) > 100:
                result["url"] = url
                return result
        except Exception as e:
            logger.warning(f"{scraper_fn.__name__} failed for {url}: {e}")
            continue

    # All direct scrapers failed (likely a SPA/JS-heavy site).
    # Try Exa semantic search to find content ABOUT the site.
    logger.info(f"Direct scraping failed for {url} — trying Exa search fallback")
    try:
        result = await _search_exa_about(url)
        if result and result.get("content") and len(result["content"]) > 100:
            result["url"] = url
            return result
    except Exception as e:
        logger.warning(f"Exa search fallback also failed for {url}: {e}")

    return {
        "url": url,
        "title": "",
        "description": "",
        "content": f"Failed to scrape {url}",
        "links": [],
        "source": "none",
    }


async def _scrape_firecrawl(url: str) -> dict | None:
    if not settings.firecrawl_api_key:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return None

        page = data.get("data", {})
        metadata = page.get("metadata", {})

        return {
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "content": page.get("markdown", ""),
            "links": _extract_links(page.get("markdown", "")),
            "source": "firecrawl",
        }


async def _scrape_exa(url: str) -> dict | None:
    if not settings.exa_api_key:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.exa.ai/contents",
            headers={
                "x-api-key": settings.exa_api_key,
                "Content-Type": "application/json",
            },
            json={
                "urls": [url],
                "text": True,
                "highlights": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            return None

        result = results[0]
        return {
            "title": result.get("title", ""),
            "description": result.get("highlights", [""])[0] if result.get("highlights") else "",
            "content": result.get("text", ""),
            "links": _extract_links(result.get("text", "")),
            "source": "exa",
        }


async def _scrape_jina(url: str) -> dict | None:
    """Jina Reader — free, just prepend r.jina.ai/"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()

        data = resp.json()
        if data.get("code") != 200:
            return None

        page = data.get("data", {})
        return {
            "title": page.get("title", ""),
            "description": page.get("description", ""),
            "content": page.get("content", ""),
            "links": _extract_links(page.get("content", "")),
            "source": "jina",
        }


async def _scrape_raw(url: str) -> dict | None:
    """Last resort — raw HTTP fetch with basic HTML stripping."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 mckoutie-bot/1.0"})
        resp.raise_for_status()
        html = resp.text

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # Extract meta description
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            html,
            re.IGNORECASE,
        )
        description = desc_match.group(1).strip() if desc_match else ""

        # Strip HTML tags for content
        content = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()

        # Truncate to reasonable length
        content = content[:10000]

        return {
            "title": title,
            "description": description,
            "content": content,
            "links": _extract_links(html),
            "source": "raw",
        }


async def _search_exa_about(url: str) -> dict | None:
    """Search Exa for content ABOUT a website when direct scraping fails (SPAs etc.)."""
    if not settings.exa_api_key:
        return None

    # Extract domain name for search query
    domain = re.sub(r"https?://", "", url).split("/")[0].replace("www.", "")
    search_query = domain.split(".")[0]  # e.g. "vibelife" from "vibelife.sh"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.exa.ai/search",
            headers={
                "x-api-key": settings.exa_api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": f"{search_query} startup product",
                "numResults": 5,
                "text": True,
                "includeDomains": [domain],
                "type": "keyword",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            # Try broader search without domain filter
            resp2 = await client.post(
                "https://api.exa.ai/search",
                headers={
                    "x-api-key": settings.exa_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": f"what is {search_query} {domain}",
                    "numResults": 5,
                    "text": True,
                    "type": "auto",
                },
            )
            resp2.raise_for_status()
            data = resp2.json()
            results = data.get("results", [])

        if not results:
            return None

        # Combine all results into one content blob
        parts = []
        title = ""
        for r in results:
            if not title and r.get("title"):
                title = r["title"]
            text = r.get("text", "")
            if text:
                parts.append(f"Source: {r.get('url', 'unknown')}\n{text[:3000]}")

        combined = "\n\n---\n\n".join(parts)
        logger.info(f"Exa search fallback found {len(results)} results, {len(combined)} chars")

        return {
            "title": title,
            "description": f"Content gathered via search about {domain}",
            "content": combined,
            "links": [r.get("url", "") for r in results if r.get("url")],
            "source": "exa-search",
        }


def _extract_links(text: str) -> list[str]:
    """Pull out interesting links from content."""
    urls = re.findall(r'https?://[^\s<>"\')\]]+', text)
    # Deduplicate and limit
    seen = set()
    unique = []
    for u in urls:
        clean = u.rstrip(".,;:")
        if clean not in seen:
            seen.add(clean)
            unique.append(clean)
    return unique[:20]
