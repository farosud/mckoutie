"""
Capybara image generator — creates themed capybara consulting images for each analysis.

Uses OpenRouter's image generation models to create variations of our
reference capybara photos, themed to the startup being analyzed.

Reference images stored in assets/capybaras/:
  the_boss.png           — capybara adjusting tie in corporate office
  the_street_analyst.png — capybara walking down city street at golden hour
  the_team.png           — army of capybaras in suits, Wolf of Wall Street energy
  the_analyst.png        — capybara grinding at a computer in an office
"""

import base64
import logging
import random
import tempfile
from pathlib import Path

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "capybaras"

# Reference capybara styles — each maps to a reference image and prompt base
CAPY_STYLES = [
    {
        "name": "The Boss",
        "file": "the_boss.png",
        "scene": "adjusting a blue tie in a corporate office, looking serious and powerful",
        "vibe": "executive portrait, boardroom energy",
    },
    {
        "name": "The Street Analyst",
        "file": "the_street_analyst.png",
        "scene": "walking confidently down a city street at golden hour",
        "vibe": "street photography, going to a meeting",
    },
    {
        "name": "The Team",
        "file": "the_team.png",
        "scene": "leading an army of capybaras in suits walking down a city street at sunset",
        "vibe": "cinematic, Wolf of Wall Street, consulting firm on the move",
    },
    {
        "name": "The Analyst",
        "file": "the_analyst.png",
        "scene": "sitting at an office desk typing on a computer, focused and grinding",
        "vibe": "late night at the consulting firm, working on the deliverable",
    },
]


def _load_reference_image(style: dict) -> str | None:
    """Load a reference capybara image as base64 for the image gen prompt."""
    image_path = ASSETS_DIR / style["file"]
    if not image_path.exists():
        logger.warning(f"Reference image not found: {image_path}")
        return None
    try:
        data = image_path.read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to load reference image {style['file']}: {e}")
        return None


def _build_prompt(startup_name: str, industry: str, unique_angle: str, style: dict) -> str:
    """Build an image generation prompt combining capybara style + startup context."""
    industry_visuals = _get_industry_visuals(industry, unique_angle)

    return (
        f"Create a variation of this capybara consultant image. "
        f"Keep the same photorealistic capybara-in-a-suit style, "
        f"but adapt the scene to incorporate elements of {industry_visuals}. "
        f"The capybara should be {style['scene']}. "
        f"Add a subtle visual reference to {startup_name} — maybe a logo-like detail, "
        f"a screen showing something related to {_get_detail(industry)}, "
        f"or environmental elements that hint at the {industry or 'tech'} industry. "
        f"Style: {style['vibe']}. "
        f"Cinematic lighting, shallow depth of field, high quality. "
        f"The capybara looks wise and slightly amused — it's a senior consultant. "
        f"No text or watermarks in the image."
    )


def _build_prompt_no_ref(startup_name: str, industry: str, unique_angle: str, style: dict) -> str:
    """Fallback prompt when no reference image is available."""
    industry_visuals = _get_industry_visuals(industry, unique_angle)

    return (
        f"A photorealistic capybara in a dark business suit {style['scene']}. "
        f"The scene subtly incorporates elements of {industry_visuals}. "
        f"Perhaps there's a small detail like a {_get_detail(industry)} visible in the scene. "
        f"Add a subtle visual reference to {startup_name}. "
        f"Style: {style['vibe']}. "
        f"Cinematic lighting, shallow depth of field, high quality, "
        f"the capybara looks wise and slightly amused. "
        f"No text or watermarks."
    )


def _get_industry_visuals(industry: str, unique_angle: str) -> str:
    """Map industry to visual elements for the image."""
    industry_lower = (industry or "").lower()

    mappings = {
        "fintech": "financial charts on screens, stock tickers, modern fintech office",
        "crypto": "blockchain visualizations, digital currencies, futuristic trading floor",
        "ai": "neural network visualizations, holographic displays, AI research lab",
        "saas": "modern software dashboards on multiple monitors, cloud architecture",
        "ecommerce": "shopping and retail, product displays, online marketplace",
        "health": "medical technology, health monitoring devices, clean clinical space",
        "education": "books, learning platforms, university campus",
        "real estate": "architectural blueprints, property listings, skyline buildings",
        "food": "restaurant kitchen, food delivery, culinary innovation",
        "gaming": "game controllers, pixel art, esports arena",
        "social": "social media feeds, community gathering, connected people",
        "climate": "renewable energy, solar panels, green technology",
        "music": "recording studio, musical instruments, sound waves",
        "travel": "airports, world maps, travel destinations",
        "legal": "law books, courtroom, legal documents",
        "defi": "DeFi dashboards, liquidity pools, yield farming interfaces",
        "nft": "digital art gallery, NFT marketplace, pixel art",
        "marketplace": "two-sided marketplace, buyers and sellers, product listings",
        "logistics": "shipping containers, supply chain maps, warehouse operations",
        "biotech": "lab equipment, DNA sequences, molecular structures",
    }

    for key, visual in mappings.items():
        if key in industry_lower:
            return visual

    if unique_angle:
        return f"a startup focused on {unique_angle[:80]}"
    return "a modern tech startup office with whiteboards and innovation"


def _get_detail(industry: str) -> str:
    """Get a small thematic detail for the scene."""
    industry_lower = (industry or "").lower()

    details = {
        "fintech": "Bloomberg terminal in the background",
        "crypto": "hardware wallet on the desk",
        "ai": "robot figurine on the shelf",
        "saas": "multiple SaaS dashboards on screens",
        "ecommerce": "shipping box with a smile logo",
        "health": "stethoscope hanging nearby",
        "education": "stack of textbooks",
        "real estate": "building model on the desk",
        "food": "artisan coffee cup",
        "gaming": "gaming keyboard glowing",
        "music": "vinyl record on the wall",
        "defi": "yield farming dashboard on screen",
        "nft": "digital art frame on the wall",
    }

    for key, detail in details.items():
        if key in industry_lower:
            return detail

    return "startup pitch deck on a nearby screen"


async def generate_capybara_image(
    startup_name: str,
    industry: str = "",
    unique_angle: str = "",
) -> Path | None:
    """
    Generate a themed capybara image for a startup analysis.

    Sends a reference capybara image + prompt to OpenRouter to create
    a variation themed to the startup being analyzed.

    Returns path to the generated image file, or None on failure.
    """
    if not settings.openrouter_api_key:
        logger.warning("No OpenRouter API key — skipping image generation")
        return None

    # Pick a random capybara style
    style = random.choice(CAPY_STYLES)
    ref_image_b64 = _load_reference_image(style)

    logger.info(f"Generating capybara image: style={style['name']}, startup={startup_name}, ref={'yes' if ref_image_b64 else 'no'}")

    # Build message content — with or without reference image
    if ref_image_b64:
        prompt = _build_prompt(startup_name, industry, unique_angle, style)
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": ref_image_b64},
            },
            {
                "type": "text",
                "text": prompt,
            },
        ]
    else:
        prompt = _build_prompt_no_ref(startup_name, industry, unique_angle, style)
        user_content = [
            {
                "type": "text",
                "text": prompt,
            },
        ]

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.5-flash-image",
                    "messages": [
                        {
                            "role": "user",
                            "content": user_content,
                        }
                    ],
                    "provider": {
                        "require_parameters": True,
                    },
                },
            )

            if response.status_code != 200:
                logger.error(f"OpenRouter image gen failed: {response.status_code} {response.text[:300]}")
                return None

            data = response.json()

            # Extract image from response — handle multiple formats
            # Log full response structure for debugging (keys only, not data)
            logger.info(f"OpenRouter response keys: {list(data.keys())}")

            choices = data.get("choices", [])
            if not choices:
                logger.error(f"No choices in OpenRouter response. Top-level keys: {list(data.keys())}")
                return None

            message = choices[0].get("message")
            if not message or not isinstance(message, dict):
                logger.error(f"No message in choices[0]: {choices[0]}")
                return None

            logger.info(f"Message keys: {list(message.keys())}")

            # Check for images in message.images first (Gemini Flash format)
            images = message.get("images")
            if images and isinstance(images, list):
                for img in images:
                    if isinstance(img, dict):
                        # Format: {"url": "data:image/...;base64,..."} or {"b64_json": "..."}
                        url = img.get("url", "")
                        if url.startswith("data:image"):
                            logger.info("Found image in message.images (url format)")
                            return _save_base64_image(url)
                        b64 = img.get("b64_json") or img.get("data") or img.get("base64", "")
                        if b64:
                            logger.info("Found image in message.images (b64 format)")
                            return _save_raw_base64(b64)
                    elif isinstance(img, str):
                        # Could be a data URL or raw base64
                        if img.startswith("data:image"):
                            logger.info("Found image in message.images (string data URL)")
                            return _save_base64_image(img)
                        if len(img) > 1000:
                            logger.info("Found image in message.images (string base64)")
                            return _save_raw_base64(img)
                logger.warning(f"message.images had {len(images)} items but none parseable")

            content = message.get("content")

            # Handle None content — only error if we also didn't find images above
            if content is None:
                logger.error(f"Got None content and no usable images. message keys: {list(message.keys())}")
                return None

            # String content — could be base64 data URL or text
            if isinstance(content, str):
                if content.startswith("data:image"):
                    return _save_base64_image(content)
                # Check if it's raw base64 (no data: prefix)
                if len(content) > 1000 and not content.startswith(("{", "[", "http")):
                    try:
                        return _save_raw_base64(content)
                    except Exception:
                        pass
                logger.error(f"Got text response instead of image (first 200 chars): {content[:200]}")
                return None

            # List/array content — multimodal response
            if isinstance(content, list):
                logger.info(f"Multimodal content: {len(content)} parts, types: {[p.get('type', type(p).__name__) if isinstance(p, dict) else type(p).__name__ for p in content]}")

                for part in content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type", "")

                    # image_url format (OpenAI-style)
                    if part_type == "image_url":
                        img_url_obj = part.get("image_url")
                        if isinstance(img_url_obj, dict):
                            url = img_url_obj.get("url", "")
                        elif isinstance(img_url_obj, str):
                            url = img_url_obj
                        else:
                            continue
                        if url.startswith("data:image"):
                            logger.info("Found image via image_url part")
                            return _save_base64_image(url)

                    # image format (inline base64 — various provider formats)
                    elif part_type == "image":
                        # Check "source" format: {"type": "base64", "media_type": "...", "data": "..."}
                        source = part.get("source")
                        if isinstance(source, dict):
                            b64_data = source.get("data", "")
                            if b64_data:
                                mime = source.get("media_type", "image/png")
                                logger.info(f"Found image via source.data ({mime})")
                                return _save_raw_base64(b64_data)
                        # Direct data/image fields
                        b64_data = part.get("data") or part.get("image", "")
                        if b64_data:
                            logger.info("Found image via image part (data field)")
                            return _save_raw_base64(b64_data)

                    # Gemini native: inline_data format
                    # {"type": "inline_data", "inline_data": {"mime_type": "image/png", "data": "..."}}
                    # Also handle without explicit type — just check for inline_data key
                    elif part_type == "inline_data" or "inline_data" in part:
                        inline = part.get("inline_data", {})
                        if isinstance(inline, dict):
                            b64_data = inline.get("data", "")
                            mime = inline.get("mime_type", "image/png")
                            if b64_data:
                                logger.info(f"Found image via inline_data ({mime})")
                                return _save_raw_base64(b64_data)

                    # Gemini via OpenRouter: parts within content items
                    # {"parts": [{"inline_data": {"mime_type": "...", "data": "..."}}]}
                    elif "parts" in part:
                        for sub_part in part.get("parts", []):
                            if isinstance(sub_part, dict) and "inline_data" in sub_part:
                                inline = sub_part["inline_data"]
                                if isinstance(inline, dict):
                                    b64_data = inline.get("data", "")
                                    mime = inline.get("mime_type", "image/png")
                                    if b64_data:
                                        logger.info(f"Found image via parts[].inline_data ({mime})")
                                        return _save_raw_base64(b64_data)

                    # text part with embedded base64
                    elif part_type == "text":
                        text = part.get("text", "")
                        if text.startswith("data:image"):
                            logger.info("Found image via text part (data URL)")
                            return _save_base64_image(text)

                # Last resort: scan all parts for any key containing base64 image data
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    for key, val in part.items():
                        if isinstance(val, str) and len(val) > 5000:
                            # Likely base64 image data — try to decode it
                            if val.startswith("data:image"):
                                logger.info(f"Found image via scan: part[{key}] (data URL)")
                                return _save_base64_image(val)
                            try:
                                decoded = base64.b64decode(val[:100])
                                # Check PNG/JPEG magic bytes
                                if decoded[:4] in (b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1'):
                                    logger.info(f"Found image via scan: part[{key}] (raw base64, magic bytes match)")
                                    return _save_raw_base64(val)
                            except Exception:
                                pass

                logger.warning(f"No image found in multimodal response ({len(content)} parts)")
                # Log sanitized structure for debugging (truncate any long strings)
                def _sanitize(obj, depth=0):
                    if depth > 3:
                        return "..."
                    if isinstance(obj, dict):
                        return {k: (f"<{len(v)} chars>" if isinstance(v, str) and len(v) > 100 else _sanitize(v, depth + 1)) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [_sanitize(item, depth + 1) for item in obj[:5]]
                    return obj
                logger.warning(f"Content structure: {_sanitize(content)}")
                return None

            logger.error(f"Unexpected content type: {type(content).__name__}")
            return None

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None


def _save_base64_image(data_url: str) -> Path:
    """Save a data:image/... URL to a temp file."""
    header, b64_data = data_url.split(",", 1)
    ext = "png" if "png" in header else "jpg"

    tmp = Path(tempfile.mktemp(suffix=f".{ext}"))
    tmp.write_bytes(base64.b64decode(b64_data))
    logger.info(f"Saved generated image to {tmp} ({tmp.stat().st_size} bytes)")
    return tmp


def _save_raw_base64(b64_data: str) -> Path:
    """Save raw base64 image data to a temp file."""
    tmp = Path(tempfile.mktemp(suffix=".png"))
    tmp.write_bytes(base64.b64decode(b64_data))
    logger.info(f"Saved generated image to {tmp} ({tmp.stat().st_size} bytes)")
    return tmp
