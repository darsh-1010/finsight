"""Man Institute scraper — Crawlee BeautifulSoupCrawler implementation.

Uses Crawlee's ``BeautifulSoupCrawler`` to fetch the listing page and
individual article pages concurrently.  Auto-retry, request de-dup,
and concurrency are handled by Crawlee.

Supports date-based filtering via ``lookback_days`` — only articles
published within the configured window are scraped.
"""

import argparse
import asyncio
import logging
from datetime import timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

from src.services.schema.article_schema import (Article, ArticleMetadata,
                                                ScrapeOutput,
                                                load_scraper_config)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


class ManInstituteScraper:
    """Scrapes research articles from the Man Institute listing page."""

    BASE_URL = "https://www.man.com"
    LISTING_URL = "https://www.man.com/maninstitute"
    SOURCE_NAME = "man_institute"

    def __init__(
        self,
        max_articles: int | None = None,
        lookback_days: int | None = None,
        output_file: str | None = None,
        max_concurrency: int | None = None,
    ):
        cfg = load_scraper_config(self.SOURCE_NAME)
        self.config = cfg
        self.max_articles = max_articles or cfg["max_articles"]
        self.lookback_days = (
            lookback_days if lookback_days is not None else cfg["lookback_days"]
        )
        self.output_file = output_file or cfg["output_file"]
        self.max_concurrency = max_concurrency or cfg.get("max_concurrency", 4)

        self._results: List[Article] = []
        self._total_found = 0
        self._total_within_window = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """Run the full pipeline synchronously (wraps async internally)."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> List[Dict]:
        """Crawlee-based async pipeline."""
        self._results = []
        self._total_found = 0
        self._total_within_window = 0

        # ── Isolate configuration to prevent asyncio.Lock event loop conflicts ─────
        config = Configuration(storage_dir=f"storage_{self.SOURCE_NAME}")

        crawler = BeautifulSoupCrawler(
            configuration=config,
            max_requests_per_crawl=self.max_articles + 1,  # listing + articles
            concurrency_settings=ConcurrencySettings(
                max_concurrency=self.max_concurrency,
                desired_concurrency=self.max_concurrency,
            ),
            request_handler_timeout=timedelta(
                seconds=self.config.get("request_timeout_sec", 30)
            ),
        )

        @crawler.router.default_handler
        async def listing_handler(context: BeautifulSoupCrawlingContext) -> None:
            """Handle the listing page — extract teasers and enqueue articles."""
            context.log.info(f"Processing listing: {context.request.url}")
            soup = context.soup

            teasers = soup.select("div.teaser__wrap")[: self.max_articles]
            self._total_found = len(teasers)

            for teaser in teasers:
                anchor = teaser.select_one("a.teaser")
                if not anchor:
                    continue

                relative_url = anchor.get("href")
                full_url = urljoin(self.BASE_URL, relative_url)

                published_date = self._safe_text(teaser, "span.details__date")

                # Date filter — skip articles outside the lookback window
                if not is_within_lookback(published_date, self.lookback_days):
                    context.log.info(
                        f"  Skipping (outside {self.lookback_days}d window): {published_date}"
                    )
                    continue

                self._total_within_window += 1

                teaser_data = {
                    "listing_title": self._safe_text(teaser, "h2.teaser__title"),
                    "category": self._safe_text(teaser, "span.details__category"),
                    "type": self._safe_text(teaser, "span.details__type"),
                    "published_date": published_date,
                    "summary": self._safe_text(teaser, "div.teaser__text"),
                    "url": full_url,
                }

                await context.add_requests(
                    [
                        Request.from_url(
                            full_url,
                            label="article",
                            user_data=teaser_data,
                        )
                    ]
                )

        @crawler.router.handler("article")
        async def article_handler(context: BeautifulSoupCrawlingContext) -> None:
            """Handle individual article pages — extract body text."""
            context.log.info(f"Processing article: {context.request.url}")
            soup = context.soup
            user_data = dict(context.request.user_data)

            heading = soup.find("h1")
            title = (
                heading.get_text(strip=True)
                if heading
                else user_data.get("listing_title", "")
            )

            # Extract author
            author_elem = soup.select_one(
                ".author__name, .article-author, [rel='author']"
            )
            author = author_elem.get_text(strip=True) if author_elem else None

            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            summary = (
                meta_desc["content"]
                if meta_desc and meta_desc.get("content")
                else user_data.get("summary", "")
            )

            # Extract article body
            paragraphs: List[str] = []
            found_heading = False
            for tag in soup.find_all(["h1", "p"]):
                if tag.name == "h1":
                    found_heading = True
                    continue
                if found_heading and tag.name == "p":
                    text = tag.get_text(strip=True)
                    if len(text) > self.config.get("min_paragraph_length", 40):
                        paragraphs.append(text)

            article_text = "\n".join(paragraphs)

            article = Article(
                source=self.SOURCE_NAME,
                url=context.request.url,
                title=title,
                content=article_text,
                summary=summary or "",
                metadata=ArticleMetadata(
                    published_date=user_data.get("published_date"),
                    author=author,
                    category=user_data.get("category"),
                    tags=[user_data.get("type")] if user_data.get("type") else [],
                ),
            )

            if len(article_text.split()) < self.config.get("low_word_threshold", 50):
                logger.warning("Low word count for: %s", article.url)

            self._results.append(article)

        await crawler.run([self.LISTING_URL])

        # Save results
        output = ScrapeOutput(
            source=self.SOURCE_NAME,
            lookback_days=self.lookback_days,
            total_found=self._total_found,
            total_within_window=self._total_within_window,
            total_scraped=len(self._results),
            articles=self._results,
        )
        output.save(self.output_file)
        logger.info(
            "Saved %d/%d articles (lookback=%dd) to %s",
            len(self._results),
            self._total_found,
            self.lookback_days,
            self.output_file,
        )

        return [a.to_dict() for a in self._results]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_text(element, selector: str) -> Optional[str]:
        """Return stripped text of the first match, or None."""
        match = element.select_one(selector)
        return match.get_text(strip=True) if match else None


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Man Institute scraper")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only scrape articles from the last N days",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Maximum number of articles to scrape",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    scraper = ManInstituteScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
