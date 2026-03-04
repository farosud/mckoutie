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

    # Method 1: Follow HTTP redirects with a real browser User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, max_redirects=15) as client:
            resp = await client.get(url, headers=headers)
            resolved = str(resp.url)
            if resolved != url and hostname not in (urlparse(resolved).hostname or ""):
                logger.info(f"Resolved {url} -> {resolved} (via redirect)")
                return resolved

            # If redirect didn't leave the short domain, parse HTML for meta refresh
            # t.co sometimes returns HTML with a meta refresh or JS redirect
            body = resp.text[:5000]

            # Check meta refresh: <meta http-equiv="refresh" content="0;url=...">
            meta_match = re.search(
                r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\d+;\s*url=([^"\'>\s]+)',
                body, re.IGNORECASE,
            )
            if meta_match:
                meta_url = meta_match.group(1).strip()
                logger.info(f"Resolved {url} -> {meta_url} (via meta refresh)")
                return meta_url

            # Check JS redirect: window.location = "..." or location.href = "..."
            js_match = re.search(
                r'(?:window\.location|location\.href)\s*=\s*["\']([^"\']+)["\']',
                body, re.IGNORECASE,
            )
            if js_match:
                js_url = js_match.group(1).strip()
                logger.info(f"Resolved {url} -> {js_url} (via JS redirect)")
                return js_url

            # Check for <a> tag with the URL (t.co pages often have a visible link)
            # e.g. <a href="https://example.com" ...>https://example.com</a>
            link_match = re.search(
                r'<a[^>]+href=["\']?(https?://[^"\'>\s]+)["\']?[^>]*>',
                body, re.IGNORECASE,
            )
            if link_match:
                link_url = link_match.group(1).strip()
                link_host = urlparse(link_url).hostname or ""
                # Make sure it's not linking back to the shortener
                if link_host and link_host != hostname:
                    logger.info(f"Resolved {url} -> {link_url} (via HTML link)")
                    return link_url

            # Check title tag for a URL (some shorteners put the target in the title)
            title_match = re.search(r'<title[^>]*>(https?://[^\s<]+)</title>', body, re.IGNORECASE)
            if title_match:
                title_url = title_match.group(1).strip()
                logger.info(f"Resolved {url} -> {title_url} (via title tag)")
                return title_url

            logger.info(f"Redirect returned same domain for {url}, using: {resolved}")
            return resolved
    except Exception as e:
        logger.warning(f"URL resolve failed for {url}: {e}")

    # Method 2: HEAD request as last resort
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, max_redirects=15) as client:
            resp = await client.head(url, headers=headers)
            resolved = str(resp.url)
            if resolved != url:
                logger.info(f"Resolved {url} -> {resolved} (via HEAD)")
                return resolved
    except Exception as e:
        logger.warning(f"HEAD resolve failed for {url}: {e}")

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
                "text": {"maxCharacters": 10000},
                "highlights": {"numSentences": 3},
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
                "type": "keyword",
                "includeDomains": [domain],
                "contents": {
                    "text": {"maxCharacters": 3000},
                },
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
                    "type": "auto",
                    "contents": {
                        "text": {"maxCharacters": 3000},
                    },
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
