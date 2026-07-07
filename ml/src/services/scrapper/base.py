"""Base abstract class for all scraper implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScraperResult:
    """Standardized output for all scrapers."""

    url: str
    status: str
    content: str = ""
    title: str | None = None
    published_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None




class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this scraper can handle the given URL."""

    @abstractmethod
    async def scrape(self, url: str) -> ScraperResult:
        """Scrape the given URL and return a ScraperResult."""
