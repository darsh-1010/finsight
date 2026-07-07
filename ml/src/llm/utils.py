"""LLM utility functions."""

import json
import re
from typing import Any


def extract_json_from_response(response: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response that may contain markdown code blocks.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON dict or None if extraction fails
    """
    # Try to find JSON in code blocks first
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON
        json_str = response.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def clean_response_text(text: str) -> str:
    """Clean LLM response text by removing artifacts.

    Args:
        text: Raw response text

    Returns:
        Cleaned text
    """
    # Remove markdown code block markers
    text = re.sub(r"```[\w]*\n?", "", text)
    # Remove extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
