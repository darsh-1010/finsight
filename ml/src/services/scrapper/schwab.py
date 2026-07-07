"""Schwab Learn page scraper — Crawlee PlaywrightCrawler + Camoufox.

Uses ``CamoufoxPlugin`` (stealthed Firefox) to bypass Schwab's WAF
that blocks headless Chromium.  Crawlee handles concurrency, retries,
and request de-duplication automatically.

Supports date-based filtering via ``lookback_days`` — articles with
a published date outside the configured window are skipped on the
listing page (before visiting the article).
"""

import argparse
import asyncio
import logging
import os
import shutil
from datetime import timedelta
from typing import Dict, List, Optional

from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.browsers import BrowserPool
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    ScrapeOutput,
    load_scraper_config,
)
from src.services.scrapper.camoufox_plugin import CamoufoxPlugin
from src.services.scrapper.resilience import (
    SCRAPER_TRY_EXCEPTIONS,
    build_playwright_retry_defaults,
    build_retry_decision,
    wait_for_any_selector,
)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


# CamoufoxPlugin is defined in src/services/scrapper/camoufox_plugin.py
# and shared across all Camoufox-based scrapers to avoid duplication.


# ------------------------------------------------------------------
# Scraper
# ------------------------------------------------------------------


class SchwabScraper:
    """Scrapes articles from the Charles Schwab Learn page.

    Pipeline:
    1. Load main Learn page with Camoufox
    2. Wait for React hydration (ArticleTile components)
    3. Extract article metadata grouped by section
    4. Filter by published date using lookback_days
    5. Enqueue each article URL that passes the filter
    6. Extract full text content from each article
    """

    TARGET_URL = "https://www.schwab.com/learn"
    SOURCE_NAME = "schwab"

    def __init__(
        self,
        lookback_days: int | None = None,
        max_articles: int | None = None,
        output_file: str | None = None,
        max_concurrency: int | None = None,
    ):
        cfg = load_scraper_config(self.SOURCE_NAME)
        self.config = cfg
        self.lookback_days = (
            lookback_days if lookback_days is not None else cfg["lookback_days"]
        )
        self.max_articles = max_articles or cfg["max_articles"]
        self.output_file = output_file or cfg["output_file"]
        self.max_concurrency = max_concurrency or cfg.get("max_concurrency", 2)

        self._articles: list[Article] = []
        self._total_found = 0
        self._total_within_window = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> list[dict] | None:
        """Run the full pipeline synchronously."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> list[dict] | None:
        """Crawlee-based async pipeline."""
        self._articles = []
        self._total_found = 0
        self._total_within_window = 0

        # Purge stale Crawlee storage to avoid 'not found in state' warnings
        storage_dir = os.path.join(os.getcwd(), f"storage_{self.SOURCE_NAME}")
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir, ignore_errors=True)

        config = Configuration(storage_dir=storage_dir)

        crawler = PlaywrightCrawler(
            configuration=config,
            concurrency_settings=ConcurrencySettings(
                max_concurrency=self.max_concurrency,
                desired_concurrency=self.max_concurrency,
            ),
            request_handler_timeout=timedelta(
                seconds=self.config.get("request_timeout_sec", 120)
            ),
            browser_pool=BrowserPool(plugins=[CamoufoxPlugin()]),
            max_requests_per_crawl=self.max_articles,
            **build_playwright_retry_defaults(self.config),
        )

        @crawler.error_handler
        async def error_handler(
            context: PlaywrightCrawlingContext, error: Exception
        ) -> None:
            """Handle and log request errors."""
            build_retry_decision(
                exc=error,
                attempt=context.request.retry_count + 1,
                max_attempts=int(self.config.get("max_request_retries", 3)),
                source=self.SOURCE_NAME,
            )

        # ---- Handler: Main Learn page ----
        @crawler.router.default_handler
        async def main_page_handler(context: PlaywrightCrawlingContext) -> None:
            """Handle the main Learn page — extract sections and enqueue articles."""
            context.log.info(
                "[PAGE_LOAD] Source: %s | URL: %s",
                self.SOURCE_NAME,
                context.request.url,
            )

            context.log.info("[SELECTOR_WAIT] Type: article_tile")
            await wait_for_any_selector(
                context.page,
                ['[data-component="ArticleTile"]'],
                timeout_ms=max(
                    self.config.get("hydration_delay_ms", 10000),
                    self.config.get("tile_timeout_ms", 20000),
                ),
                source=self.SOURCE_NAME,
            )

            # Check for block page
            page_content = await context.page.content()
            block_signals = [
                "Access Denied",
                "Please enable JS",
                "unable to authorize your request",
            ]
            if any(signal in page_content for signal in block_signals):
                context.log.error("Bot detection triggered — blocked!")
                return

            # Wait for article tiles
            try:
                await context.page.wait_for_selector(
                    '[data-component="ArticleTile"]',
                    timeout=self.config.get("tile_timeout_ms", 20000),
                )
                context.log.info("Article tiles detected.")
            except SCRAPER_TRY_EXCEPTIONS:
                context.log.warning(
                    "Article tiles not found — page may not have hydrated."
                )

            # Extract sections with articles (including date from tile metadata)
            sections = await context.page.evaluate("""
                () => {
                    const results = [];
                    const headings = Array.from(document.querySelectorAll('h2'));

                    headings.forEach(h2 => {
                        const headingText = h2.innerText.trim();
                        if (!headingText) return;

                        const sectionData = {
                            heading: headingText,
                            articles: []
                        };

                        let container = h2.closest('[data-component="Mosaic"]') ||
                                        h2.parentElement.nextElementSibling;

                        if (!container || !container.querySelector('[data-component="ArticleTile"]')) {
                            const parent = h2.closest('[data-component="Container"]');
                            if (parent) container = parent;
                        }

                        if (container) {
                            const tiles = Array.from(
                                container.querySelectorAll('[data-component="ArticleTile"]')
                            );
                            tiles.forEach(tile => {
                                const linkElem = tile.querySelector('a[data-component="link"]');
                                if (!linkElem) return;

                                const title = linkElem.getAttribute('data-dl-link.name') ||
                                              tile.querySelector('h3')?.innerText.trim() ||
                                              linkElem.getAttribute('aria-label');

                                const url = linkElem.href;

                                const metaElem = tile.querySelector(
                                    '[data-component="LockupDisclosure"]'
                                );
                                const metaText = metaElem ? metaElem.innerText.trim() : "";

                                let type = "";
                                let date = "";
                                if (metaText.includes('|')) {
                                    const parts = metaText.split('|');
                                    type = parts[0].trim();
                                    date = parts[1].trim();
                                } else {
                                    type = metaText;
                                }

                                sectionData.articles.push({
                                    title: title,
                                    url: url,
                                    type: type,
                                    date: date
                                });
                            });
                        }

                        if (sectionData.articles.length > 0) {
                            results.push(sectionData);
                        }
                    });

                    return results;
                }
            """)

            total_articles = sum(len(s["articles"]) for s in sections)
            self._total_found = total_articles
            context.log.info(
                f"Found {total_articles} articles across {len(sections)} sections"
            )

            # Enqueue each article for content scraping (with date filtering)
            for section in sections:
                for article in section["articles"]:
                    if not article.get("url"):
                        continue

                    # Date filter — skip articles outside the lookback window
                    article_date = article.get("date", "")
                    if not is_within_lookback(article_date, self.lookback_days):
                        short_title = article.get("title", "")[:40]
                        context.log.info(
                            f"  Skipping (outside {self.lookback_days}d window):"
                            f" {article_date} — {short_title}"
                        )
                        continue

                    self._total_within_window += 1

                    await context.add_requests(
                        [
                            Request.from_url(
                                article["url"],
                                label="article",
                                user_data={
                                    "title": article.get("title", ""),
                                    "section": section["heading"],
                                    "type": article.get("type", ""),
                                    "listing_date": article_date,
                                },
                            )
                        ]
                    )

        # ---- Handler: Article pages ----
        @crawler.router.handler("article")
        async def article_handler(context: PlaywrightCrawlingContext) -> None:
            """Handle article pages — extract full text content and metadata."""
            url = context.request.url
            title = context.request.user_data.get("title", "Unknown")[:60]
            context.log.info(f"Scraping article: {title}")

            await wait_for_any_selector(
                context.page,
                ["article", "[role='main']", "main", "h1"],
                timeout_ms=self.config.get("article_settle_delay_ms", 3000) + 5000,
                source=self.SOURCE_NAME,
            )

            content = await context.page.evaluate("""
                () => {
                    const article = document.querySelector('article') ||
                                   document.querySelector('[role="main"]') ||
                                   document.querySelector('main') ||
                                   document.body;

                    const toRemove = article.querySelectorAll(
                        'script, style, nav, footer, header'
                    );
                    toRemove.forEach(el => el.remove());

                    const fullText = article.innerText.trim();
                    const title = document.querySelector('h1')?.innerText.trim() ||
                                 document.title;
                    const metaDesc = document.querySelector(
                        'meta[name="description"]'
                    )?.content || '';

                    // Extract published date
                    const publishedDate =
                        document.querySelector('meta[property="article:published_time"]')?.content ||
                        document.querySelector('meta[name="date"]')?.content ||
                        document.querySelector('time[datetime]')?.getAttribute('datetime') ||
                        null;

                    // Extract author
                    const author =
                        document.querySelector('meta[name="author"]')?.content ||
                        document.querySelector('.author-name, .byline')?.innerText.trim() ||
                        null;

                    return {
                        title: title,
                        summary: metaDesc,
                        full_text: fullText,
                        word_count: fullText.split(/\\s+/).length,
                        published_date: publishedDate,
                        author: author,
                    };
                }
            """)

            user_data = context.request.user_data

            article = Article(
                source=self.SOURCE_NAME,
                url=url,
                title=content.get("title", user_data.get("title", "")),
                content=content.get("full_text", ""),
                summary=content.get("summary", ""),
                metadata=ArticleMetadata(
                    published_date=content.get("published_date")
                    or user_data.get("listing_date"),
                    author=content.get("author"),
                    category=user_data.get("section"),
                    tags=[user_data.get("type")] if user_data.get("type") else [],
                ),
            )
            self._articles.append(article)

        # Run the crawler
        await crawler.run([self.TARGET_URL])

        # Save results
        output = ScrapeOutput(
            source=self.SOURCE_NAME,
            lookback_days=self.lookback_days,
            total_found=self._total_found,
            total_within_window=self._total_within_window,
            total_scraped=len(self._articles),
            articles=self._articles,
        )
        output.save(self.output_file)
        logger.info(
            "Saved %d/%d articles (lookback=%dd) to %s",
            len(self._articles),
            self._total_found,
            self.lookback_days,
            self.output_file,
        )

        return [a.to_dict() for a in self._articles] if self._articles else None


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Schwab Learn scraper")
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
    scraper = SchwabScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
