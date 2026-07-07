"""Morgan Stanley Insights scraper — Crawlee PlaywrightCrawler + Camoufox.

Uses ``CamoufoxPlugin`` (stealthed Firefox) to bypass Morgan Stanley's
TLS fingerprint detection that blocks Chromium.  Crawlee handles
concurrency, retries, and request de-duplication automatically.

Supports date-based filtering via ``lookback_days`` — articles outside
the window are discarded after scraping (dates extracted from article
meta tags).
"""

import argparse
import asyncio
import logging
import os
import shutil
from datetime import timedelta

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
    wait_for_post_action_settle,
)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


# CamoufoxPlugin is defined in src/services/scrapper/camoufox_plugin.py
# and shared across all Camoufox-based scrapers to avoid duplication.


# ------------------------------------------------------------------
# Scraper
# ------------------------------------------------------------------


class MorganStanleyScraper:
    """Scrapes insight articles from the Morgan Stanley website.

    Pipeline:
    1. Load main insights hub with Camoufox
    2. Click "View More" to reveal all content
    3. Extract & categorise links (topic pages vs articles)
    4. Enqueue topic pages to discover more articles
    5. Enqueue all unique article URLs
    6. Extract full content from each article page
    7. Filter by published_date against lookback_days
    """

    INSIGHTS_URL = "https://www.morganstanley.com/insights"
    SOURCE_NAME = "morgan_stanley"

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

        # Group secondary config to stay within Pylint class attribute limits
        self.settings = {
            "request_timeout_sec": cfg.get("request_timeout_sec", 120),
            "content_settle_delay_ms": cfg.get("content_settle_delay_ms", 3000),
            "load_more_delay_ms": cfg.get("load_more_delay_ms", 2000),
            "max_load_more_clicks": cfg.get("max_load_more_clicks", 30),
            "selector_timeout_ms": cfg.get("selector_timeout_ms", 30000),
            "cookie_timeout_ms": cfg.get("cookie_timeout_ms", 2000),
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
                seconds=self.settings["request_timeout_sec"]
            ),
            browser_pool=BrowserPool(plugins=[CamoufoxPlugin()]),
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
        crawler.router.default_handler(self._main_page_handler)
        crawler.router.handler("topic")(self._topic_handler)
        crawler.router.handler("article")(self._article_handler)

        # Run the crawler starting from the main insights page
        await crawler.run([self.INSIGHTS_URL])

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
            "[SCRAPE_FINISH] Source: %s | Saved %s/%s articles to %s",
            self.SOURCE_NAME,
            len(self._articles),
            self._total_found,
            self.output_file,
        )

        return [a.to_dict() for a in self._articles]

    # ──────────────────────────────────────────────
    # Request Handlers
    # ──────────────────────────────────────────────

    async def _main_page_handler(self, context: PlaywrightCrawlingContext) -> None:
        """Handle the main insights page — load content and extract links."""
        context.log.info(
            "[PAGE_LOAD] Source: %s | URL: %s", self.SOURCE_NAME, context.request.url
        )

        await wait_for_any_selector(
            context.page,
            ["a[href*='/insights/']"],
            timeout_ms=self.settings["selector_timeout_ms"],
            source=self.SOURCE_NAME,
        )

        # Wait for at least one insight link to appear in DOM
        try:
            await context.page.wait_for_selector(
                "a[href*='/insights/']",
                timeout=self.settings["selector_timeout_ms"],
                state="attached",
            )
            context.log.info(
                "[SELECTOR_READY] Source: %s | Type: main_links", self.SOURCE_NAME
            )

            # Try to accept cookies if banner is present
            try:
                cookie_btn = await context.page.wait_for_selector(
                    "#onetrust-accept-btn-handler",
                    timeout=self.settings["cookie_timeout_ms"],
                )
                if cookie_btn:
                    await cookie_btn.click(force=True)
                    context.log.info(
                        "[COOKIES] Source: %s | Action: accepted", self.SOURCE_NAME
                    )
            except SCRAPER_TRY_EXCEPTIONS:
                pass

        except SCRAPER_TRY_EXCEPTIONS as exc:
            context.log.error(
                "[LOAD_ERROR] Source: %s | Error: %s | Simple: Failed to load insights hub.",
                self.SOURCE_NAME,
                str(exc)[:50],
            )
            html = await context.page.content()
            with open("ms_error.html", "w", encoding="utf-8") as file:
                file.write(html)
            return

        # STEP 2: Click "View More" to reveal all content
        context.log.info(f"[LOAD_MORE] Source: {self.SOURCE_NAME} | Status: starting")
        clicks = 0
        while clicks < self.settings["max_load_more_clicks"]:
            button = await context.page.query_selector(
                ".button--viewmore-insights.loadMoreCardsAutomation"
            )
            if not button or not await button.is_visible():
                break
            context.log.info(
                f"[CLICK] Source: {self.SOURCE_NAME} | Element: view_more | Count: {clicks + 1}"
            )
            await button.click(force=True)
            await wait_for_post_action_settle(
                context.page,
                [".button--viewmore-insights.loadMoreCardsAutomation"],
                timeout_ms=self.settings["load_more_delay_ms"] + 5000,
                source=self.SOURCE_NAME,
            )
            clicks += 1
        context.log.info(
            f"[LOAD_MORE] Source: {self.SOURCE_NAME} | Status: complete | Clicks: {clicks}"
        )

        # STEP 3: Extract and categorise links
        links = await context.page.evaluate("""
            () => {
                const items = [];
                const seen = new Set();
                document.querySelectorAll("a[href*='/insights/']").forEach(a => {
                    const title = a.innerText.trim();
                    const url = a.href;
                    if (title && title.length > 5 && !seen.has(url)) {
                        seen.add(url);
                        items.push({ title, url });
                    }
                });
                return items;
            }
        """)
        context.log.info(f"[EXTRACT] Source: {self.SOURCE_NAME} | Links: {len(links)}")

        topics, direct, _ = self._categorize_links(links)
        context.log.info(
            f"[CATEGORIZE] Source: {self.SOURCE_NAME} | Direct: {len(direct)} | Topics: {len(topics)}"
        )

        self._total_found = len(direct)

        # Enqueue topic pages
        for topic in topics:
            await context.add_requests(
                [
                    Request.from_url(
                        topic["url"],
                        label="topic",
                        user_data={"title": topic["title"]},
                    )
                ]
            )

        # Enqueue article pages
        for art in direct:
            await context.add_requests(
                [
                    Request.from_url(
                        art["url"],
                        label="article",
                        user_data={"title": art["title"]},
                    )
                ]
            )

    async def _topic_handler(self, context: PlaywrightCrawlingContext) -> None:
        """Handle topic pages — extract article links and enqueue them."""
        context.log.info(
            f"[TOPIC_LOAD] Source: {self.SOURCE_NAME} | URL: {context.request.url}"
        )

        await wait_for_any_selector(
            context.page,
            ["a[href*='/insights/articles/']"],
            timeout_ms=self.settings["selector_timeout_ms"],
            source=self.SOURCE_NAME,
        )

        # Click "Load More" on topic page
        selectors = [
            ".button--viewmore-insights",
            ".loadMoreCardsAutomation",
            "button[class*='load-more']",
            "button[class*='view-more']",
        ]
        clicks = 0
        while clicks < self.settings["max_load_more_clicks"]:
            found = False
            for selector in selectors:
                button = await context.page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    await wait_for_post_action_settle(
                        context.page,
                        ["a[href*='/insights/articles/']"],
                        timeout_ms=self.settings["load_more_delay_ms"] + 5000,
                        source=self.SOURCE_NAME,
                    )
                    clicks += 1
                    found = True
                    break
            if not found:
                break

        # Extract article links from topic page
        articles = await context.page.evaluate("""
            () => {
                const items = [];
                const seen = new Set();
                document.querySelectorAll("a[href*='/insights/articles/']").forEach(a => {
                    const title = a.innerText.trim();
                    const url = a.href;
                    if (title && title.length > 5 && !seen.has(url)) {
                        seen.add(url);
                        items.push({ title, url });
                    }
                });
                return items;
            }
        """)
        context.log.info(
            f"[TOPIC_EXTRACT] Source: {self.SOURCE_NAME} | Articles: {len(articles)}"
        )

        self._total_found += len(articles)

        for art in articles:
            await context.add_requests(
                [
                    Request.from_url(
                        art["url"],
                        label="article",
                        user_data={"title": art["title"]},
                    )
                ]
            )

    async def _article_handler(self, context: PlaywrightCrawlingContext) -> None:
        """Handle article pages — extract full content and metadata."""
        url = context.request.url
        title = context.request.user_data.get("title", "Unknown")
        context.log.info(
            f"[ARTICLE_LOAD] Source: {self.SOURCE_NAME} | Title: {title[:60]}"
        )

        await wait_for_any_selector(
            context.page,
            ["h1"],
            timeout_ms=self.settings["selector_timeout_ms"],
            require_visible=True,
            source=self.SOURCE_NAME,
        )

        content = await context.page.evaluate("""
            () => {
                const data = {
                    paragraphs: [],
                    full_text: ""
                };

                const mainTitle = document.querySelector('h1');
                if (mainTitle) {
                    data.main_heading = mainTitle.innerText.trim();
                }

                document.querySelectorAll('p').forEach(p => {
                    const text = p.innerText.trim();
                    if (text && text.length > 20) {
                        data.paragraphs.push(text);
                    }
                });

                data.full_text = data.paragraphs.join(' ');

                // Extract metadata
                const metaDesc = document.querySelector('meta[name="description"]');
                if (metaDesc) data.summary = metaDesc.content;

                const metaDate = document.querySelector('meta[property="article:published_time"]');
                if (metaDate) data.published_date = metaDate.content;

                if (!data.published_date) {
                    const contentDate = document.querySelector('meta[name="content_publishedAt"]');
                    if (contentDate) data.published_date = contentDate.content;
                }

                // Try other date patterns
                if (!data.published_date) {
                    const timeElem = document.querySelector('time[datetime]');
                    if (timeElem) data.published_date = timeElem.getAttribute('datetime');
                }
                // Morgan Stanley specific — the visible date span
                if (!data.published_date) {
                    const msDateElem = document.querySelector(
                        '.cmp_articleHeader_date, .cmp-text-eyebrow ~ .cmp_articleHeader_date'
                    );
                    if (msDateElem) data.published_date = msDateElem.innerText.trim();
                }
                if (!data.published_date) {
                    const dateElem = document.querySelector('.date, .article-date, .publish-date');
                    if (dateElem) data.published_date = dateElem.innerText.trim();
                }

                // Extract author
                const authorMeta = document.querySelector(
                    'meta[name="author"]'
                ) || document.querySelector('meta[name="content_author"]');
                if (authorMeta) {
                    data.author = authorMeta.content;
                } else {
                    const authorElem = document.querySelector('.author, .byline, [rel="author"]');
                    if (authorElem) data.author = authorElem.innerText.trim();
                }

                // Extract category from breadcrumbs or tags
                const categoryElem = document.querySelector('.breadcrumb a:last-child, .category-label');
                if (categoryElem) data.category = categoryElem.innerText.trim();

                return data;
            }
        """)

        # Date filter — discard articles outside the lookback window
        published_date = content.get("published_date")
        if not is_within_lookback(published_date, self.lookback_days):
            context.log.info(
                f"[DATE_SKIP] Source: {self.SOURCE_NAME} | Date: {published_date}"
            )
            return

        article = Article(
            source=self.SOURCE_NAME,
            url=url,
            title=content.get("main_heading", title),
            content=content.get("full_text", ""),
            summary=content.get("summary", ""),
            metadata=ArticleMetadata(
                published_date=published_date,
                author=content.get("author"),
                category=content.get("category"),
            ),
        )
        self._articles.append(article)

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _categorize_links(links: list[dict]):
        """Split links into topic pages, article pages, and other."""
        topics, articles, others = [], [], []
        for item in links:
            url = item["url"]
            if "/insights/articles/" in url:
                articles.append(item)
            elif "/insights/topics/" in url:
                topics.append(item)
            else:
                others.append(item)
        return topics, articles, others


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Morgan Stanley Insights scraper")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only keep articles from the last N days",
    )
    parser.add_argument(
        "--max_articles",
        type=int,
        default=None,
        help="Maximum number of articles to scrape",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("[SCRAPER_INIT] Source: MORGAN_STANLEY")
    scraper = MorganStanleyScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
