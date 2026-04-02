"""LLM-powered keyword expansion for user discovery.

Uses the Anthropic Claude API (already configured in the project) to expand
seed keywords into a broader set of related search terms.
"""

import json
import logging
from typing import Optional

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a social media marketing analyst specialising in Twitter/X conversations \
in African markets. Your task is to expand seed keywords into a comprehensive set \
of related search phrases that real people would use in tweets.

Rules:
1. Generate 10-15 related keywords/phrases.
2. Include variations in spelling, slang, pidgin English, and local expressions.
3. Include both problem statements and solution-seeking phrases.
4. Keep phrases short (2-5 words) — they will be used as Twitter search queries.
5. Return ONLY a JSON array of strings, no other text.
"""

USER_PROMPT_TEMPLATE = """\
Expand these seed keywords into related Twitter search phrases.
Focus on how people in {location} would naturally express these topics on Twitter.

Seed keywords: {keywords}

Return a JSON array of 10-15 expanded keyword phrases.
"""


async def expand_keywords(
    seed_keywords: list[str],
    location: str = "Nigeria",
) -> list[str]:
    """Call Claude to expand seed keywords into related search phrases.

    Args:
        seed_keywords: The user's original keywords (e.g. ["Fuel price pain"]).
        location: Target market location for contextual expansion.

    Returns:
        A list of expanded keyword strings.
    """
    if not settings.anthropic_api_key:
        log.warning("ANTHROPIC_API_KEY not set — returning seed keywords only")
        return seed_keywords

    user_message = USER_PROMPT_TEMPLATE.format(
        location=location,
        keywords=", ".join(f'"{kw}"' for kw in seed_keywords),
    )

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": settings.anthropic_api_version,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.anthropic_timeout_seconds) as client:
            response = await client.post(
                settings.anthropic_api_base,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        # Extract text from Claude's response
        content_blocks = data.get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text += block.get("text", "")

        # Parse the JSON array from the response
        expanded = _parse_keyword_list(text)
        log.info(
            "Expanded %d seed keywords into %d search phrases",
            len(seed_keywords),
            len(expanded),
        )
        return expanded

    except httpx.HTTPStatusError as exc:
        log.error("Anthropic API error: %s — %s", exc.response.status_code, exc.response.text)
        return seed_keywords
    except Exception as exc:
        log.error("Keyword expansion failed: %s", exc)
        return seed_keywords


def _parse_keyword_list(text: str) -> list[str]:
    """Extract a JSON array of strings from LLM output, handling markdown fences."""
    cleaned = text.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return [str(item).strip() for item in result if item]
    except json.JSONDecodeError:
        log.warning("Could not parse LLM output as JSON: %s", cleaned[:200])

    # Fallback: try to extract quoted strings
    import re
    matches = re.findall(r'"([^"]+)"', text)
    if matches:
        return matches

    return []
