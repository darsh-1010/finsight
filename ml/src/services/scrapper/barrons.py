"""
Barron's Markets News Scraper
Using Crawlee Python with PlaywrightCrawler

Organic navigation — only START_URL is hardcoded:
  Step 1 → barrons.com    : find "Markets" in navbar -> <span class="emotion-osralh">Markets</span>
  Step 2 → Markets page   : find "Markets" section -> <h1 class="nk-headline-heading emotion-kgja09">Markets</h1>
  Step 3 → Collect links  : collect article links published within TIME_WINDOW_DAYS = 1
  Step 4 → Each article   : scrape full text, extract published_date, save to output folder
"""

import argparse
import asyncio
import logging
import re
from datetime import timedelta

from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    load_scraper_config,
)
from src.services.scrapper.date_filter import is_within_lookback, parse_date
from src.services.scrapper.resilience import (
    build_playwright_retry_defaults,
    wait_for_any_selector,
)
from src.utils.logger import get_logger
from src.services.scrapper.utils import dismiss_overlays, save_results, safe_filename

# ── Configuration ─────────────────────────────────────────────────────────────
SOURCE_NAME = "barrons"
START_URL = "https://www.barrons.com/"

logger = get_logger(__name__)


def get_config():
    """Get the scraper configuration."""
    return load_scraper_config(SOURCE_NAME)


# ── Helpers ───────────────────────────────────────────────────────────────────



# ── BarronsScraper Class ──────────────────────────────────────────────────────
class BarronsScraper:
    """Encapsulates the crawler state and route handlers for Barron's scraping."""

    def __init__(self, lookback_days: int, max_articles: int, output_file: str):
        self.lookback_days = lookback_days
        self.max_articles = max_articles
        self.output_file = output_file

        self.scraped_articles: list[Article] = []
        self.stats = {"total_found": 0, "total_within_window": 0}

    async def handle_article(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle individual article extraction."""
        page = ctx.page
        url = ctx.request.url
        logger.info("[ARTICLE_EXTRACT] URL: %s", url)

        meta = await page.evaluate("""() => {
            let title = '';
            const titleSels = ['h1.article-header__headline', 'h1[class*="headline"]', 'h1'];
            for (const sel of titleSels) {
                const el = document.querySelector(sel);
                if (el?.innerText?.trim()) { title = el.innerText.trim(); break; }
            }
            let author = null;
            const authorSels = ['[class*="author"]', '[class*="byline"]', '.article-header__author'];
            for (const sel of authorSels) {
                const el = document.querySelector(sel);
                if (el?.innerText?.trim()) { author = el.innerText.trim(); break; }
            }
            let dateStr = null;
            const dateSels = ['time', '.article-header__timestamp', '[class*="timestamp"]', '[class*="date"]'];
            for (const sel of dateSels) {
                const el = document.querySelector(sel);
                if (el?.getAttribute('datetime')) { dateStr = el.getAttribute('datetime'); break; }
                if (el?.innerText?.trim()) { dateStr = el.innerText.trim(); break; }
            }
            const summary = document.querySelector('meta[name="description"]')?.getAttribute('content') || '';
            const body = Array.from(document.querySelectorAll('.article-body p, .article-content p, article p, p'))
                .map(p => p.innerText.trim()).filter(t => t.length > 50).join('\\n\\n');
            return { title, author, dateStr, summary, body };
        }""")

        pub_date = parse_date(meta.get("dateStr"))
        iso_pdate = pub_date.isoformat() if pub_date else None

        if not is_within_lookback(iso_pdate, self.lookback_days):
            logger.info("[FILTER_SKIP] Status: Outside Window | Date: %s", iso_pdate)
            return

        self.stats["total_within_window"] += 1
        article = Article(
            source="barrons",
            url=url,
            title=meta["title"] or "Untitled",
            content=meta["body"],
            summary=meta["summary"],
            metadata=ArticleMetadata(
                published_date=iso_pdate, author=meta.get("author"), category="Markets"
            ),
        )
        self.scraped_articles.append(article)
        logger.info("[SCRAPE_COMPLETE] Article: %s", article.title[:60])

    async def handle_listing(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle Markets listing page."""
        page = ctx.page
        logger.info("[LISTING_PAGE] Collecting links from: %s", ctx.request.url)

        links = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const selectors = ['article', 'div[class*="BarronsCard"]', 'div[class*="Story"]'];
            let elements = [];
            selectors.forEach(sel => {
                elements = elements.concat(Array.from(document.querySelectorAll(sel)));
            });
            if (elements.length === 0) elements = Array.from(document.querySelectorAll('a[href*="/articles/"]'));

            elements.forEach(el => {
                const a = el.tagName === 'A' ? el : el.querySelector('a[href*="/articles/"]');
                if (!a) return;
                const href = a.href;
                if (seen.has(href)) return;
                seen.add(href);
                const titleEl = el.querySelector('h2, h3, [class*="Headline"]');
                const text = titleEl ? titleEl.innerText.trim() : "";
                let dateStr = el.querySelector('time')?.innerText?.trim() || '';
                results.push({ href, text, dateStr });
            });
            return results;
        }""")

        self.stats["total_found"] += len(links)
        to_queue = []
        for lnk in links:
            pub = parse_date(lnk.get("dateStr"))
            if pub and not is_within_lookback(pub.isoformat(), self.lookback_days):
                continue
            to_queue.append(lnk["href"].split("?")[0])

        if to_queue:
            await ctx.add_requests(to_queue)
        logger.info("[QUEUED_LINKS] Count: %d", len(to_queue))

    async def handle_homepage_navigation(self, ctx: PlaywrightCrawlingContext) -> None:
        """Find Markets link on homepage."""
        page = ctx.page
        logger.info("[HOMEPAGE_NAV] Searching for Markets category")
        try:
            link = page.locator("a:has(span:has-text('Markets'))").first
            if await link.count() > 0:
                href = await link.get_attribute("href")
                full = (
                    href
                    if href.startswith("http")
                    else f"{START_URL.rstrip('/')}{href}"
                )
                await ctx.add_requests([full])
                return
        except (TimeoutError, AttributeError, TypeError):
            pass
        await ctx.add_requests(["https://www.barrons.com/market-data"])

    async def universal_handler(self, ctx: PlaywrightCrawlingContext) -> None:
        """Route context dynamically to correct page handler method."""
        page = ctx.page
        url = ctx.request.url
        logger.info("[ROUTING] URL: %s", url)

        await wait_for_any_selector(
            page,
            ["main", "article", "a[href*='/articles/']"],
            timeout_ms=20000,
        )
        await dismiss_overlays(page)

        is_homepage = url.strip("/").rstrip("/") == START_URL.strip("/").rstrip("/")
        is_article = "/articles/" in url or bool(re.search(r"SB\d{15,}", url))

        if is_article:
            await self.handle_article(ctx)
            return

        if is_homepage:
            await self.handle_homepage_navigation(ctx)
        else:
            await self.handle_listing(ctx)

    async def run(self) -> None:
        """Run the Playwright crawler."""
        scraper_cfg = load_scraper_config(SOURCE_NAME)
        retry_settings = build_playwright_retry_defaults(scraper_cfg)

        config = Configuration(storage_dir=f"storage_{SOURCE_NAME}")

        crawler = PlaywrightCrawler(
            configuration=config,
            headless=True,
            browser_type="chromium",
            max_requests_per_crawl=self.max_articles,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1,
                max_concurrency=3,
                desired_concurrency=3,
            ),
            navigation_timeout=timedelta(seconds=90),
            request_handler_timeout=timedelta(seconds=120),
            browser_launch_options={
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--blink-settings=imagesEnabled=false",
                    "--memory-pressure-off",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certificate-errors",
                    "--ignore-certificate-errors-spki-list",
                ],
                "handle_sigint": False,
                "handle_sigterm": False,
                "handle_sighup": False,
            },
            browser_new_context_options={
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1920, "height": 1080},
                "ignore_https_errors": True,
            },
            **retry_settings,
        )

        @crawler.pre_navigation_hook
        async def customize_request(ctx: PlaywrightCrawlingContext) -> None:
            ctx.page.set_default_navigation_timeout(90_000)

            await ctx.page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,image/apng,*/*;q=0.8"
                    ),
                    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            try:
                ctx.goto_options["wait_until"] = "domcontentloaded"
            except (AttributeError, TypeError):
                pass

            await ctx.block_requests(
                extra_url_patterns=[
                    ".*google-analytics.*",
                    ".*doubleclick.*",
                    ".*googletagservices.*",
                    ".*facebook.*",
                    ".*outbrain.*",
                    ".*chartbeat.*",
                ]
            )

        crawler.router.default_handler(self.universal_handler)

        logger.info("=" * 60)
        logger.info("Barron's Markets News Scraper")
        logger.info("Entry      : %s", START_URL)
        logger.info("Time window: last %d day(s)", self.lookback_days)
        logger.info("Output     : %s", self.output_file)
        logger.info("=" * 60)

        await crawler.run([START_URL])

        logger.info("\n%s", "=" * 60)
        logger.info("Done. Articles scraped: %d", len(self.scraped_articles))
        logger.info(
            "      Within %dd window: %d",
            self.lookback_days,
            self.stats["total_within_window"],
        )
        logger.info("=" * 60)
        save_results(
            self.scraped_articles,
            self.stats,
            self.lookback_days,
            self.output_file,
            SOURCE_NAME,
        )


async def main(
    lookback_days: int, max_articles: int, output_file: str | None = None
) -> None:
    """Main async entry point to run the BarronsScraper."""
    scraper_cfg = load_scraper_config(SOURCE_NAME)
    final_output_file = output_file or scraper_cfg["output_file"]

    scraper = BarronsScraper(
        lookback_days=lookback_days,
        max_articles=max_articles,
        output_file=final_output_file,
    )
    await scraper.run()


def run_cli():
    """Run CLI parsing and execute scraper."""
    parser = argparse.ArgumentParser(description="Barron's Markets News Scraper")
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

    scraper_cfg_main = get_config()
    lookback_val = (
        args.lookback_days
        if args.lookback_days is not None
        else scraper_cfg_main["lookback_days"]
    )
    max_art_val = (
        args.max_articles
        if args.max_articles is not None
        else scraper_cfg_main["max_articles"]
    )
    out_file_val = scraper_cfg_main["output_file"]

    asyncio.run(
        main(
            lookback_days=lookback_val,
            max_articles=max_art_val,
            output_file=out_file_val,
        )
    )


if __name__ == "__main__":
    run_cli()
