"""Seeking Alpha scraper — Crawlee PlaywrightCrawler + Camoufox.

Uses ``CamoufoxPlugin`` (stealthed Firefox) to bypass Seeking Alpha's
aggressive anti-bot measures (403 on plain HTTP, paywall modals).
Crawlee handles concurrency, retries, and request de-duplication.

Supports date-based filtering via ``lookback_days`` — articles with
a published date outside the window are discarded after scraping.
"""

import argparse
import asyncio
import logging
import os
import random
import shutil
from datetime import timedelta

from camoufox import AsyncNewBrowser
from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.browsers import (
    BrowserPool,
    PlaywrightBrowserController,
    PlaywrightBrowserPlugin,
)
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.errors import SessionError
from typing_extensions import override

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    ScrapeOutput,
    load_scraper_config,
)
from src.services.scrapper.resilience import (
    build_playwright_retry_defaults,
    build_retry_decision,
    wait_for_any_selector,
)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# CamoufoxPlugin — stealthed Firefox browser for anti-bot bypass
# ------------------------------------------------------------------


class CamoufoxPlugin(PlaywrightBrowserPlugin):
    """Browser plugin that uses Camoufox (stealthed Firefox)."""

    @override
    async def new_browser(self) -> PlaywrightBrowserController:
        if not self._playwright:
            raise RuntimeError("Playwright browser plugin is not initialized.")
        return PlaywrightBrowserController(
            browser=await AsyncNewBrowser(
                self._playwright, **self._browser_launch_options
            ),
            max_open_pages_per_browser=1,
            header_generator=None,
        )


# ------------------------------------------------------------------
# Scraper
# ------------------------------------------------------------------


class SeekingAlphaScraper:
    """Scrapes market-news articles from Seeking Alpha.

    Pipeline:
    1. Load market-news listing page with Camoufox
    2. Extract article links and titles from the news feed
    3. Follow pagination (``?page=N``)
    4. Visit each article page to extract full content
    5. Filter by published_date against lookback_days
    """

    LISTING_URL = "https://seekingalpha.com/market-news"
    SOURCE_NAME = "seeking_alpha"

    def __init__(
        self,
        lookback_days: int | None = None,
        max_articles: int | None = None,
        output_file: str | None = None,
        max_concurrency: int | None = None,
    ):
        cfg = load_scraper_config(self.SOURCE_NAME)
        self.lookback_days = (
            lookback_days if lookback_days is not None else cfg["lookback_days"]
        )
        self.max_articles = max_articles or cfg["max_articles"]
        self.output_file = output_file or cfg["output_file"]
        self.max_concurrency = max_concurrency or cfg.get("max_concurrency", 2)
        self.retry_settings = build_playwright_retry_defaults(cfg)

        # Group secondary config to satisfy Pylint attribute limit
        self.settings = {
            "request_timeout_sec": cfg.get("request_timeout_sec", 120),
            "page_settle_delay_ms": cfg.get("page_settle_delay_ms", 5000),
            "max_pages": cfg.get("max_pages", 5),
        }

        self._articles: list[Article] = []
        self._total_found = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> list[dict]:
        """Run the full pipeline synchronously."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> list[dict]:
        """Crawlee-based async pipeline."""
        self._articles = []
        self._total_found = 0

        # Purge stale Crawlee storage
        storage_dir = os.path.join(os.getcwd(), f"storage_{self.SOURCE_NAME}")
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir, ignore_errors=True)

        config = Configuration(storage_dir=storage_dir)

        crawler = PlaywrightCrawler(
            configuration=config,
            concurrency_settings=ConcurrencySettings(
                max_concurrency=1, desired_concurrency=1
            ),
            request_handler_timeout=timedelta(
                seconds=self.settings["request_timeout_sec"]
            ),
            browser_pool=BrowserPool(
                plugins=[CamoufoxPlugin()],
                retire_browser_after_page_count=4,
            ),
            ignore_http_error_status_codes=[403],
            max_requests_per_crawl=self.max_articles,
            **self.retry_settings,
        )

        @crawler.error_handler
        async def error_handler(
            context: PlaywrightCrawlingContext, error: Exception
        ) -> None:
            """Handle and log request errors."""
            build_retry_decision(
                exc=error,
                attempt=context.request.retry_count + 1,
                max_attempts=int(self.retry_settings.get("max_request_retries", 3)),
                source=self.SOURCE_NAME,
            )

        # Register handlers
        crawler.router.default_handler(self._listing_handler)
        crawler.router.handler("article")(self._article_handler)

        await crawler.run([self.LISTING_URL])

        # Save results
        output = ScrapeOutput(
            source=self.SOURCE_NAME,
            lookback_days=self.lookback_days,
            total_found=self._total_found,
            total_within_window=len(self._articles),
            total_scraped=len(self._articles),
            articles=self._articles,
        )
        output.save(self.output_file)
        logger.info(
            "[SCRAPE_FINISH] Source: %s | Saved %s articles to %s",
            self.SOURCE_NAME,
            len(self._articles),
            self.output_file,
        )

        return [a.to_dict() for a in self._articles]

    # ──────────────────────────────────────────────
    # Request Handlers
    # ──────────────────────────────────────────────

    async def _listing_handler(self, context: PlaywrightCrawlingContext) -> None:
        """Handle market-news listing page — extract and enqueue articles."""
        context.log.info(
            "[LISTING_LOAD] Source: %s | URL: %s", self.SOURCE_NAME, context.request.url
        )

        # Human-like movement jitter before starting
        await asyncio.sleep(random.uniform(2.0, 5.0))

        await wait_for_any_selector(
            context.page,
            ["[data-test-id='post-list-item']", "article"],
            timeout_ms=30000,
            source=self.SOURCE_NAME,
        )

        # Enqueue first N pages
        url_obj = context.request.url
        if "page=" not in url_obj:
            for i in range(2, self.settings["max_pages"] + 1):
                page_url = f"{self.LISTING_URL}?page={i}"
                await context.add_requests([Request.from_url(page_url)])

        # Extract links from current page
        links = await context.page.evaluate("""
            () => {
                const items = [];
                const seen = new Set();
                document.querySelectorAll("a[href*='/news/']").forEach(a => {
                    const title = a.innerText.trim();
                    const url = a.href;
                    if (title && title.length > 10 && !seen.has(url)) {
                        seen.add(url);
                        items.push({ title, url });
                    }
                });
                return items;
            }
        """)

        context.log.info(
            "[LISTING_EXTRACT] Source: %s | Count: %s", self.SOURCE_NAME, len(links)
        )
        self._total_found += len(links)

        for item in links:
            await context.add_requests(
                [
                    Request.from_url(
                        item["url"],
                        label="article",
                        user_data={"title": item["title"]},
                    )
                ]
            )

    async def _article_handler(self, context: PlaywrightCrawlingContext) -> None:
        """Handle article detail pages."""
        url = context.request.url
        title = context.request.user_data.get("title", "Unknown")
        context.log.info(
            "[ARTICLE_LOAD] Source: %s | Title: %s", self.SOURCE_NAME, title[:60]
        )

        # Mandatory anti-bot cooling before each article scrape
        await asyncio.sleep(random.uniform(3.0, 7.0))

        # Check for immediate 403 / "Access Denied"
        page_content = await context.page.content()
        if "Access Denied" in page_content or "403 Forbidden" in page_content:
            context.log.warning(
                "[BLOCK_DETECTED] Source: %s | Action: retry_rotate", self.SOURCE_NAME
            )
            raise SessionError("Seeking Alpha 403 block")

        await wait_for_any_selector(
            context.page,
            ["[data-test-id='article-content']", "article", ".article-body"],
            timeout_ms=20000,
            require_visible=True,
            source=self.SOURCE_NAME,
        )

        content = await context.page.evaluate("""
            () => {
                const data = {
                    paragraphs: [],
                    full_text: ""
                };

                const artBody = document.querySelector("[data-test-id='article-content']") 
                             || document.querySelector("article");
                
                if (artBody) {
                    artBody.querySelectorAll('p').forEach(p => {
                        const text = p.innerText.trim();
                        if (text && text.length > 20) {
                            data.paragraphs.push(text);
                        }
                    });
                }
                
                data.full_text = data.paragraphs.join(' ');

                // Metadata
                const metaDesc = document.querySelector('meta[name="description"]');
                if (metaDesc) data.summary = metaDesc.content;

                const metaDate = document.querySelector('meta[property="article:published_time"]');
                if (metaDate) data.published_date = metaDate.content;

                const authorMeta = document.querySelector('meta[name="author"]');
                if (authorMeta) data.author = authorMeta.content;

                return data;
            }
        """)

        # Date filter
        published_date = content.get("published_date")
        if not is_within_lookback(published_date, self.lookback_days):
            context.log.info(
                "[DATE_SKIP] Source: %s | Date: %s", self.SOURCE_NAME, published_date
            )
            return

        article = Article(
            source=self.SOURCE_NAME,
            url=url,
            title=title,
            content=content.get("full_text", ""),
            summary=content.get("summary", ""),
            metadata=ArticleMetadata(
                published_date=published_date,
                author=content.get("author"),
            ),
        )
        self._articles.append(article)


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Seeking Alpha News scraper")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only keep articles from the last N days",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger.info("[SCRAPER_INIT] Source: SEEKING_ALPHA")
    scraper = SeekingAlphaScraper(lookback_days=args.lookback_days)
    scraper.scrape()


if __name__ == "__main__":
    main()
