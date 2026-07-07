"""Jefferies Insights scraper — Crawlee PlaywrightCrawler implementation.

Uses Crawlee's ``PlaywrightCrawler`` to scrape insight articles from
Jefferies across multiple categories.  Crawlee handles concurrency,
request de-duplication, retries, and fingerprint rotation automatically.

Supports date-based filtering via ``lookback_days`` — articles outside
the window are discarded after scraping (Jefferies doesn't expose dates
on listing pages).
"""

import argparse
import asyncio
import logging
import os
import shutil
from datetime import timedelta

from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
    PlaywrightPreNavCrawlingContext,
)

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    ScrapeOutput,
    load_scraper_config,
)
from src.services.scrapper.resilience import (
    build_playwright_retry_defaults,
    wait_for_any_selector,
)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


class JefferiesScraper:
    """Scrapes insight articles from the Jefferies website.

    Iterates through multiple category listing pages, extracts article
    links, then visits each article page to capture full text.
    Pagination is followed automatically.
    """

    TARGET_URLS = [
        "https://www.jefferies.com/insights/",
        "https://www.jefferies.com/insights/category/boardroom-intelligence/",
        "https://www.jefferies.com/insights/category/the-big-picture/",
        "https://www.jefferies.com/insights/category/sustainability-and-culture/",
    ]
    SOURCE_NAME = "jefferies"

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
        self.max_concurrency = max_concurrency or cfg.get("max_concurrency", 4)

        self._articles: list[Article] = []
        self._total_found = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> list[dict]:
        """Run the full scraping pipeline synchronously."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> list[dict]:
        """Crawlee-based async pipeline."""
        self._articles = []
        self._total_found = 0

        # crawler = PlaywrightCrawler(
        #     concurrency_settings=ConcurrencySettings(
        #         max_concurrency=self.max_concurrency,
        #         desired_concurrency=self.max_concurrency,
        #     ),
        #     request_handler_timeout=timedelta(seconds=self.request_timeout_sec),
        #     headless=True,
        #     browser_type="chromium",
        # )

        # browser_launch_options={"args": ["--no-sandbox", "--disable-setuid-sandbox"]},

        # ── Purge stale Crawlee storage to avoid asyncio.Lock event loop conflicts ──────
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
                seconds=self.config.get("request_timeout_sec", 60)
            ),
            headless=True,
            browser_type="chromium",
            max_requests_per_crawl=self.max_articles,
            browser_launch_options={
                "args": ["--no-sandbox", "--disable-setuid-sandbox"]
            },
            **build_playwright_retry_defaults(self.config),
        )

        @crawler.pre_navigation_hook
        async def setup_page(context: PlaywrightPreNavCrawlingContext) -> None:
            """Configure page before navigation."""
            context.page.set_default_navigation_timeout(
                self.config.get("navigation_timeout_ms", 60000)
            )

        @crawler.router.default_handler
        async def listing_handler(context: PlaywrightCrawlingContext) -> None:
            """Handle category listing pages — extract article links."""
            url = context.request.url
            category = context.request.user_data.get(
                "category", self._category_name(url)
            )

            context.log.info(f"Processing listing: {url} (category: {category})")

            await wait_for_any_selector(
                context.page,
                ["article", ".post", ".insight-card"],
                timeout_ms=self.config.get("navigation_timeout_ms", 60000),
            )

            # Extract article links using JS
            page_articles = await context.page.evaluate("""
                () => {
                    const articles = [];
                    const items = document.querySelectorAll('article, .post, .insight-card');

                    items.forEach(item => {
                        const linkElem = item.querySelector('h2 a')
                            || item.querySelector('h3 a') || item.querySelector('a');
                        if (!linkElem) return;

                        const title = linkElem.innerText.trim();
                        const url = linkElem.href;

                        if (url &&
                            url.includes('/insights/') &&
                            !url.includes('/category/') &&
                            !url.includes('/page/') &&
                            url.length > "https://www.jefferies.com/insights/".length + 5) {

                            articles.push({
                                title: title,
                                url: url
                            });
                        }
                    });
                    return articles;
                }
            """)

            self._total_found += len(page_articles)
            context.log.info(f"  Found {len(page_articles)} articles on this page.")

            # Enqueue each article for processing
            for art in page_articles:
                await context.add_requests(
                    [
                        Request.from_url(
                            art["url"],
                            label="article",
                            user_data={"category": category, "title": art["title"]},
                        )
                    ]
                )

            # Check for next page
            next_url = await context.page.evaluate("""
                () => {
                    const nextBtn = document.querySelector('.next.page-numbers') ||
                                   document.querySelector('a.next') ||
                                   Array.from(document.querySelectorAll('.pagination a, .nav-links a'))
                                       .find(a => a.innerText.toLowerCase().includes('next'));
                    return nextBtn ? nextBtn.href : null;
                }
            """)

            if next_url and next_url != url:
                context.log.info(f"  Found next page: {next_url}")
                await context.add_requests(
                    [
                        Request.from_url(
                            next_url,
                            label="listing",
                            user_data={"category": category},
                        )
                    ]
                )

        @crawler.router.handler("listing")
        async def next_listing_handler(context: PlaywrightCrawlingContext) -> None:
            """Handle paginated listing pages — same logic as default."""
            await listing_handler(context)

        @crawler.router.handler("article")
        async def article_handler(context: PlaywrightCrawlingContext) -> None:
            """Handle individual article pages — extract full text and metadata."""
            url = context.request.url
            category = context.request.user_data.get("category", "general_insights")
            context.log.info(f"Processing article: {url}")

            content = await context.page.evaluate("""
                () => {
                    const article = document.querySelector('article') ||
                                   document.querySelector('.post-content') ||
                                   document.querySelector('.entry-content') ||
                                   document.body;

                    const clone = article.cloneNode(true);

                    const toRemove = clone.querySelectorAll(
                        'script, style, nav, footer, header, .social-share, .related-posts'
                    );
                    toRemove.forEach(el => el.remove());

                    const title = document.querySelector('h1')?.innerText.trim() || document.title;
                    const bodyText = clone.innerText.trim();

                    // Extract date from meta tags or visible elements
                    const publishedDate =
                        document.querySelector('meta[property="article:published_time"]')?.content ||
                        document.querySelector('meta[name="date"]')?.content ||
                        document.querySelector('time[datetime]')?.getAttribute('datetime') ||
                        document.querySelector('.post-date, .date, .published-date')?.innerText.trim() ||
                        null;

                    // Extract author
                    const author =
                        document.querySelector('meta[name="author"]')?.content ||
                        document.querySelector('.author-name, .byline, [rel="author"]')?.innerText.trim() ||
                        null;

                    // Extract meta description
                    const summary =
                        document.querySelector('meta[name="description"]')?.content ||
                        document.querySelector('meta[property="og:description"]')?.content ||
                        '';

                    // Extract tags
                    const tags = Array.from(
                        document.querySelectorAll('.tag, .post-tag, [rel="tag"]')
                    ).map(t => t.innerText.trim()).filter(t => t.length > 0);

                    return {
                        title,
                        content: bodyText,
                        word_count: bodyText.split(/\\s+/).length,
                        published_date: publishedDate,
                        author,
                        summary,
                        tags,
                    };
                }
            """)

            # Date filter — discard articles outside the lookback window
            published_date = content.get("published_date")
            if not is_within_lookback(published_date, self.lookback_days):
                context.log.info(
                    f"  Discarding (outside {self.lookback_days}d window): {published_date}"
                )
                return

            article = Article(
                source=self.SOURCE_NAME,
                url=url,
                title=context.request.user_data.get("title", content.get("title", "")),
                content=content.get("content", ""),
                summary=content.get("summary", ""),
                metadata=ArticleMetadata(
                    published_date=published_date,
                    author=content.get("author"),
                    category=category,
                    tags=content.get("tags", []),
                ),
            )
            self._articles.append(article)

        # Run crawler with all target listing URLs
        await crawler.run(self.TARGET_URLS)

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
            "Saved %d/%d articles (lookback=%dd) to %s",
            len(self._articles),
            self._total_found,
            self.lookback_days,
            self.output_file,
        )

        return [a.to_dict() for a in self._articles]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _category_name(url: str) -> str:
        """Derive a human-readable category name from the URL."""
        if "category" in url:
            return url.strip("/").split("/")[-1]
        return "general_insights"


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Jefferies Insights scraper")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only keep articles from the last N days",
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
    scraper = JefferiesScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
