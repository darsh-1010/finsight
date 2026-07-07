"""Prompt loading utilities for LLM interactions."""

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """Load and manage prompts from markdown files.

    Prompts are stored in config/prompts/ as markdown files for
    easy editing and version control.
    """

    _prompts_dir: ClassVar[Path] = (
        Path(__file__).resolve().parent.parent.parent / "config" / "prompts"
    )
    # Fallback for Docker environment if relative path fails
    if not _prompts_dir.exists():
        _docker_path = Path("/app/config/prompts")
        if _docker_path.exists():
            _prompts_dir = _docker_path
    _cache: ClassVar[dict[str, str]] = {}

    @classmethod
    def pre_load_all(cls) -> None:
        """Pre-load all prompts into memory."""
        logger.info("Pre-loading all prompts...")
        for name in cls.list_prompts():
            cls._get_cached(name)
        logger.info(f"Successfully pre-loaded {len(cls._cache)} prompts")

    @classmethod
    def load(cls, name: str, **kwargs) -> str:
        """Load a prompt by name and optionally format it.

        Args:
            name: Prompt name (without .md extension)
            **kwargs: Variables to substitute in the prompt

        Returns:
            Formatted prompt string

        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        prompt = cls._get_cached(name)

        if kwargs:
            return prompt.format(**kwargs)
        return prompt

    @classmethod
    def _get_cached(cls, name: str) -> str:
        """Get prompt from cache or load from file."""
        if name not in cls._cache:
            cls._cache[name] = cls._load_from_file(name)
        return cls._cache[name]

    @classmethod
    def _load_from_file(cls, name: str) -> str:
        """Load prompt content from markdown file."""
        file_path = cls._prompts_dir / f"{name}.md"

        if not file_path.exists():
            logger.error(f"Prompt file not found: {file_path}")
            raise FileNotFoundError(f"Prompt '{name}' not found at {file_path}")

        content = file_path.read_text(encoding="utf-8")
        logger.debug(f"Loaded prompt: {name} ({len(content)} chars)")

        return content

    @classmethod
    def reload(cls, name: str | None = None) -> None:
        """Clear cache and reload prompt(s).

        Args:
            name: Specific prompt to reload, or None for all
        """
        if name:
            cls._cache.pop(name, None)
            logger.info(f"Cleared prompt cache: {name}")
        else:
            cls._cache.clear()
            logger.info("Cleared all prompt cache")

    @classmethod
    def list_prompts(cls) -> list[str]:
        """List all available prompt names."""
        return [f.stem for f in cls._prompts_dir.glob("*.md")]


@lru_cache(maxsize=10)
def get_prompt(name: str) -> str:
    """Quick utility to get a prompt by name.

    Args:
        name: Prompt name (e.g., 'query_expansion', 'ticker_resolution')

    Returns:
        Prompt content as string
    """
    return PromptLoader.load(name)
