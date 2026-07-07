"""Utility functions for scrapers."""

import asyncio
import re

from src.services.schema.article_schema import ScrapeOutput
from src.utils.logger import get_logger

logger = get_logger(__name__)


def safe_filename(text: str, max_len: int = 80) -> str:
    """Sanitize string for use as a filename."""
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len] or "untitled"


def save_results(
    scraped_articles: list,
    stats: dict,
    lookback_days: int,
    output_file: str,
    source_name: str,
) -> None:
    """Save scraped articles to JSON output file."""
    if not scraped_articles:
        logger.warning("Nothing to save.")
        return

    output = ScrapeOutput(
        source=source_name,
        lookback_days=lookback_days,
        total_found=stats["total_found"],
        total_within_window=stats["total_within_window"],
        total_scraped=len(scraped_articles),
        articles=scraped_articles,
    )

    output.save(output_file)
    logger.info("JSON saved to %s", output_file)


async def dismiss_overlays(page) -> None:
    """Close cookie banners and modals."""
    for sel in [
        "#onetrust-accept-btn-handler",
        "button[id*='accept']",
        "button[id*='cookie']",
        "button[aria-label*='Accept']",
        "button[class*='accept']",
        ".close-modal",
        "[data-test='cookie-accept']",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2000)
                await asyncio.sleep(0.3)
                break
        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            Exception,
        ) as exc:
            logger.debug("Failed checking/clicking cookie locator %s: %s", sel, exc)
