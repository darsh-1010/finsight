"""Unified article schema used by all scrapers.

Every scraper outputs articles conforming to this schema so that
downstream consumers (vector stores, APIs, etc.) get a consistent
structure regardless of the source website.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import yaml

SCRAPER_VERSION = "crawlee-1.0"


# ------------------------------------------------------------------
# Article dataclass
# ------------------------------------------------------------------


@dataclass
class ArticleMetadata:
    """Secondary metadata for articles."""

    published_date: str | None = None
    author: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    scraped_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    scraper_version: str = SCRAPER_VERSION


@dataclass
class Article:
    """Unified article representation across all scrapers."""

    source: str
    url: str
    title: str
    content: str = ""
    summary: str = ""
    metadata: ArticleMetadata = field(default_factory=ArticleMetadata)

    @property
    def word_count(self) -> int:
        """Compute word count dynamically from content.

        This is a computed property — it is never stored or serialised.
        All scrapers that check `article.word_count` use this safely.
        """
        return len(self.content.split()) if self.content else 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serialisable dictionary."""
        d = asdict(self)
        # Flatten for backward compatibility in JSON output
        meta = d.pop("metadata")
        d.update(meta)
        return d


# ------------------------------------------------------------------
# Output envelope
# ------------------------------------------------------------------


@dataclass
class ScrapeOutput:
    """Top-level output wrapper with run-level metadata."""

    source: str
    lookback_days: int
    total_found: int  # Articles discovered on the site
    total_within_window: int  # Articles that passed the date filter
    total_scraped: int  # Articles successfully scraped with content
    articles: list[Article] = field(default_factory=list)
    scraped_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scrape_metadata": {
                "source": self.source,
                "scraped_at": self.scraped_at,
                "lookback_days": self.lookback_days,
                "total_found": self.total_found,
                "total_within_window": self.total_within_window,
                "total_scraped": self.total_scraped,
            },
            "articles": [a.to_dict() for a in self.articles],
        }

    def save(self, output_path: str) -> None:
        """Write the full output to a JSON file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# Config loader
# ------------------------------------------------------------------


def _expand_env_vars(content: str) -> str:
    """Expand environment variables in the format ${VAR:-DEFAULT} or ${VAR}.

    If the variable is not set and no default is provided, the original
    placeholder string is returned.
    """
    # Matches ${VAR} or ${VAR:-DEFAULT}
    pattern = re.compile(r"\${(\w+)(?::-([^}]*))?}")

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # return the environment variable, or the default, or the original string
        val = os.getenv(var_name)
        if val is not None:
            return val
        if default_value is not None:
            return default_value
        return match.group(0)

    return pattern.sub(replacer, content)


def load_scraper_config(scraper_name: str) -> dict[str, Any]:
    """Load per-scraper settings from ``config/scraper_config.yaml``.

    Falls back to sensible defaults if the file or key is missing.
    """
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config", "scraper_config.yaml"
    )
    defaults = {
        "enabled": True,
        "max_articles": 50,
        "lookback_days": 1,
        "output_file": f"outputs/{scraper_name}_articles.json",
    }
    try:
        with open(config_path, encoding="utf-8") as fh:
            content = fh.read()
            expanded_content = _expand_env_vars(content)
        cfg = yaml.safe_load(expanded_content) or {}

        scraper_cfg = cfg.get("scrapers", {}).get(scraper_name, {})
        defaults.update(scraper_cfg)

        # Ensure numeric fields are correctly cast (env vars return strings)
        for key in ["max_articles", "lookback_days", "interval_days"]:
            if key in defaults and defaults[key] is not None:
                try:
                    defaults[key] = int(defaults[key])
                except (ValueError, TypeError):
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning(
                        f"Failed to cast {key} to int for {scraper_name}: {defaults[key]}"
                    )
    except FileNotFoundError:
        pass
    return defaults
