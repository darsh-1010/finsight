"""Centralized JSON parsing utilities for LLM responses."""

import json
import re
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMResponseParser:
    """Parse and clean JSON responses from LLM.

    Handles common issues like:
    - Markdown code blocks
    - Extra whitespace
    - Trailing commas (non-standard JSON)
    """

    # Pattern to match markdown code blocks
    _CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

    @classmethod
    def parse(cls, response: str) -> dict[str, Any]:
        """Parse LLM response to JSON dictionary.

        Args:
            response: Raw LLM response string

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValueError: If parsing fails
        """
        cleaned = cls._clean_response(response)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            logger.debug(f"Failed content: {cleaned[:200]}...")
            raise ValueError(f"Invalid JSON from LLM: {e}") from e

    @classmethod
    def parse_safe(cls, response: str, default: dict | None = None) -> dict[str, Any]:
        """Parse LLM response, returning default on failure.

        Args:
            response: Raw LLM response string
            default: Default value if parsing fails

        Returns:
            Parsed JSON or default value
        """
        try:
            return cls.parse(response)
        except ValueError:
            return default or {}

    @classmethod
    def _clean_response(cls, response: str) -> str:
        """Clean LLM response for JSON parsing."""
        text = response.strip()

        # Extract from markdown code block if present
        match = cls._CODE_BLOCK_PATTERN.search(text)
        if match:
            text = match.group(1).strip()
        else:
            # Try manual removal of code block markers
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

        return text.strip()

    @classmethod
    def extract_field(cls, response: str, field: str, default: Any = None) -> Any:
        """Extract a specific field from JSON response.

        Args:
            response: Raw LLM response
            field: Field name to extract
            default: Default if field not found

        Returns:
            Field value or default
        """
        try:
            data = cls.parse(response)
            return data.get(field, default)
        except ValueError:
            return default


def parse_llm_json(response: str) -> dict[str, Any]:
    """Quick utility to parse LLM JSON response.

    Args:
        response: Raw LLM response string

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If parsing fails
    """
    return LLMResponseParser.parse(response)
