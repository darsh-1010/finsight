"""
Deutsche Bank Outlooks Scraper
Using Crawlee Python with PlaywrightCrawler

Organic navigation — only START_URL is hardcoded:
  Step 1 → db.com        : find "news" in home page
  Step 2 → news          : find all articles within the lookback window
  Step 3 → each article  : scrape full text, save to output folder
"""

import argparse
import asyncio
import datetime
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
    SCRAPER_TRY_EXCEPTIONS,
    build_playwright_retry_defaults,
    wait_for_any_selector,
)
from src.utils.logger import get_logger
from src.services.scrapper.utils import dismiss_overlays, save_results, safe_filename

# ── ONLY hardcoded URL ───────────────────────────────────────────────────────
SOURCE_NAME = "deutsche_bank"
START_URL = "https://www.db.com/"

logger = get_logger(__name__)


def get_config():
    """Get the scraper configuration."""
    return load_scraper_config(SOURCE_NAME)


# ── Helpers ──────────────────────────────────────────────────────────────────



# ── Crawler class ─────────────────────────────────────────────────────────────
class DeutscheBankScraper:
    """Encapsulates the crawler state and route handlers for Deutsche Bank scraping."""

    def __init__(self, lookback_days: int, max_articles: int, output_file: str):
        self.lookback_days = lookback_days
        self.max_articles = max_articles
        self.output_file = output_file

        self.scraped_articles: list[Article] = []
        self.article_titles: dict[str, str] = {}
        self.article_dates: dict[str, str] = {}  # clean_url → ISO date string
        self.stats = {"total_found": 0, "total_within_window": 0}

    async def handle_article(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle individual article page scraping."""
        page = ctx.page
        url = ctx.request.url
        logger.info("[STEP 3] Article Discovery: %s", url)

        clean_url = url.split("#")[0].split("?")[0]
        date_str = self.article_dates.get(clean_url) or self.article_dates.get(url)

        if not date_str:
            match = re.search(r"(\d{8})", url)
            if match:
                date_str = match.group(1)

        if not date_str:
            date_text = await page.evaluate("""() => {
                const timeEl = document.querySelector('time');
                return timeEl ? timeEl.getAttribute('datetime') || timeEl.innerText : null;
            }""")
            if date_text:
                date_str = date_text.strip()

        article_dt = parse_date(date_str)
        if article_dt:
            now_utc = datetime.datetime.now(datetime.UTC)
            days_old = (now_utc - article_dt).days
            if not is_within_lookback(article_dt.isoformat(), self.lookback_days):
                logger.info(
                    "  [X] Skipping article (older than %d days): %s",
                    self.lookback_days,
                    url,
                )
                return
            logger.info(
                "  [-] Article is %d days old (Within %d days limit)",
                days_old,
                self.lookback_days,
            )
        else:
            logger.info("  [?] Could not determine date, scraping anyway.")

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.5)

        scraped_data = await page.evaluate("""() => {
            let title = '';
            for (const sel of ['h1','[class*="headline"]','[class*="title"]']) {
                const el = document.querySelector(sel);
                if (el?.innerText?.trim()) { title = el.innerText.trim(); break; }
            }
            title = title || document.title;

            const body = Array.from(document.querySelectorAll('p'))
                .map(p => p.innerText.trim())
                .filter(t => t.length > 25)
                .join('\\n\\n');

            return { title, body };
        }""")

        bad_titles = ["Deutsche Bank", "You might be interested in"]
        dict_title = self.article_titles.get(clean_url) or self.article_titles.get(url)
        if dict_title and (
            not scraped_data["title"]
            or any(b in scraped_data["title"] for b in bad_titles)
        ):
            scraped_data["title"] = dict_title

        article = Article(
            source="deutsche_bank",
            url=url,
            title=scraped_data["title"],
            content=scraped_data["body"],
            summary=scraped_data.get("summary", ""),
            metadata=ArticleMetadata(
                published_date=article_dt.isoformat() if article_dt else None,
                author=scraped_data.get("author"),
                category="News",
            ),
        )

        logger.info(
            "  [✓] Scraped: %s... (%d chars)", article.title[:50], len(article.content)
        )
        self.scraped_articles.append(article)
        self.stats["total_within_window"] += 1

    async def handle_news_hub(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle news hub page to collect article links."""
        page = ctx.page
        url = ctx.request.url
        logger.info(
            "[STEP 2] News hub → collecting article links from last %d days",
            self.lookback_days,
        )

        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)

        links = await page.evaluate(
            """(currentUrl) => {
            const seen = new Set();
            return Array.from(document.querySelectorAll('article'))
                .map(article => {
                    const a = article.querySelector('h3 a') || article.querySelector('a[href]');
                    const time = article.querySelector('time');
                    return {
                        href: a ? a.href : null,
                        text: a ? (a.innerText || '').replace(/\\s+/g, ' ').trim() : null,
                        date: time ? time.getAttribute('datetime') : null
                    };
                })
                .filter(x => x.href && !seen.has(x.href) && seen.add(x.href));
        }""",
            url,
        )

        logger.info("  [✓] Found %d article link(s)", len(links))
        self.stats["total_found"] += len(links)

        to_queue = []
        for link in links:
            clean_url = link["href"].split("#")[0].split("?")[0]
            self.article_titles[clean_url] = link["text"] or ""

            date_str = link.get("date")
            if not date_str:
                match = re.search(r"(\d{8})", clean_url)
                if match:
                    date_str = match.group(1)

            art_dt = parse_date(date_str)
            if art_dt:
                if is_within_lookback(art_dt.isoformat(), self.lookback_days):
                    self.article_dates[clean_url] = art_dt.isoformat()
                    to_queue.append(clean_url)
                    logger.info(
                        "    [+] (<= %d days) %s -> %s",
                        self.lookback_days,
                        link["text"],
                        clean_url,
                    )
                else:
                    logger.info(
                        "    [-] (> %d days) %s -> %s",
                        self.lookback_days,
                        link["text"],
                        clean_url,
                    )
            else:
                to_queue.append(clean_url)
                logger.info("    [?] %s -> %s", link["text"], clean_url)

        logger.info("[!] Added %d request(s) for scraping.", len(to_queue))
        if to_queue:
            await ctx.add_requests(to_queue)

    async def handle_homepage(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle homepage to locate News and Thought Leadership links."""
        page = ctx.page
        logger.info("[STEP 1] Homepage → looking for News and Thought Leadership links")

        # 1. Thought Leadership Extraction directly from homepage
        try:
            h2_tl = page.locator("h2.id-0c91b2b3-35a8-4ae1-8afe-862ddb26eed1").first
            if await h2_tl.count() > 0:
                logger.info("  [✓] Found Thought Leadership h2")
                links = await page.evaluate("""() => {
                    const h2 = document.querySelector('h2.id-0c91b2b3-35a8-4ae1-8afe-862ddb26eed1');
                    if (!h2) return [];
                    const container = h2.closest('.cms-row') || document.body;
                    return Array.from(container.querySelectorAll('article.news-stream-entry'))
                        .map(article => {
                            const a = article.querySelector('h3 a') || article.querySelector('a[href]');
                            const time = article.querySelector('time');
                            return {
                                href: a ? a.href : null,
                                text: a ? (a.innerText || '').replace(/\\s+/g, ' ').trim() : null,
                                date: time ? time.getAttribute('datetime') : null
                            };
                        })
                        .filter(x => x.href);
                }""")

                logger.info(
                    "  [✓] Found %d Thought Leadership articles on homepage", len(links)
                )
                self.stats["total_found"] += len(links)

                tl_queue = []
                for link in links:
                    clean_url = link["href"].split("#")[0].split("?")[0]
                    self.article_titles[clean_url] = link["text"] or ""
                    art_dt = parse_date(link.get("date"))
                    if not art_dt:
                        tl_queue.append(clean_url)
                        logger.info(
                            "    [?] Unknown TL date format %s", link.get("date")
                        )
                        continue

                    if is_within_lookback(art_dt.isoformat(), self.lookback_days):
                        self.article_dates[clean_url] = art_dt.isoformat()
                        tl_queue.append(clean_url)
                        logger.info(
                            "    [+] (TL <= %d days) %s",
                            self.lookback_days,
                            link["text"],
                        )
                    else:
                        logger.info(
                            "    [-] (TL > %d days) %s",
                            self.lookback_days,
                            link["text"],
                        )

                if tl_queue:
                    await ctx.add_requests(tl_queue)
        except SCRAPER_TRY_EXCEPTIONS as e:
            logger.error("  [!] Failed Thought Leadership discovery: %s", e)

        # 2. News Hub Discovery
        try:
            h2 = page.locator("h2.container-headline:has-text('News')").first
            if await h2.count() > 0:
                logger.info("  [✓] Found News h2")
                news_link = page.locator(
                    "a[href*='/media/news'], a[href*='/news']"
                ).first
                if await news_link.count() > 0:
                    href = await news_link.get_attribute("href")
                    href = href.split("?")[0]
                    full_url = (
                        "https://www.db.com" + href if href.startswith("/") else href
                    )
                    logger.info("  [✓] Found News link: %s", full_url)
                    await ctx.add_requests([full_url])
                    return

            logger.info("  [!] Did not find specific h2, looking for any news link...")
            news_link = page.locator("a[href*='/media/news'], a[href*='/news']").first
            if await news_link.count() > 0:
                href = await news_link.get_attribute("href")
                href = href.split("?")[0]
                full_url = "https://www.db.com" + href if href.startswith("/") else href
                logger.info("  [✓] Found News link: %s", full_url)
                await ctx.add_requests([full_url])
                return

        except SCRAPER_TRY_EXCEPTIONS as e:
            logger.error("  [!] Failed Homepage Discovery: %s", e)

        # Fallback
        await ctx.add_requests(["https://www.db.com/media/news"])

    async def universal_handler(self, ctx: PlaywrightCrawlingContext) -> None:
        """Route crawlee context dynamically to correct handler method."""
        page = ctx.page
        url = ctx.request.url
        logger.info("Processing: %s", url)

        await wait_for_any_selector(
            page,
            ["main", "article", "a[href*='/news']"],
            timeout_ms=15000,
        )
        await dismiss_overlays(page)

        is_homepage = url.strip("/") == START_URL.strip("/")
        is_article = (
            "/news/detail/" in url
            or "/media/news/detail/" in url
            or "flow.db.com" in url
            or "/what-next/" in url
        )
        is_news_hub = ("/news" in url or "/media/news" in url) and not is_article

        if is_article:
            await self.handle_article(ctx)
        elif is_news_hub:
            await self.handle_news_hub(ctx)
        elif is_homepage:
            await self.handle_homepage(ctx)

    async def run(self) -> None:
        """Execute the PlaywrightCrawler crawl loop."""
        scraper_cfg = load_scraper_config(SOURCE_NAME)
        retry_settings = build_playwright_retry_defaults(scraper_cfg)

        config = Configuration(storage_dir=f"storage_{SOURCE_NAME}")
        crawler = PlaywrightCrawler(
            configuration=config,
            headless=True,
            browser_type="chromium",
            max_requests_per_crawl=self.max_articles,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=2,
                max_concurrency=5,
                desired_concurrency=3,
            ),
            navigation_timeout=timedelta(seconds=60),
            request_handler_timeout=timedelta(seconds=120),
            browser_launch_options={
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ]
            },
            **retry_settings,
        )

        @crawler.pre_navigation_hook
        async def block_trackers(ctx: PlaywrightCrawlingContext) -> None:
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
                    ".*chartbeat.*",
                    ".*hotjar.*",
                ]
            )

        crawler.router.default_handler(self.universal_handler)

        logger.info("=" * 60)
        logger.info("Deutsche Bank Scraper")
        logger.info("Entry : %s", START_URL)
        logger.info("Out   : %s", self.output_file)
        logger.info("=" * 60)

        await crawler.run([START_URL])

        logger.info("\n%s", "=" * 60)
        logger.info("Done. Articles scraped: %d", len(self.scraped_articles))
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
    """Main async entry point to run the DeutscheBankScraper."""
    scraper_cfg = load_scraper_config(SOURCE_NAME)
    final_output_file = output_file or scraper_cfg["output_file"]

    scraper = DeutscheBankScraper(
        lookback_days=lookback_days,
        max_articles=max_articles,
        output_file=final_output_file,
    )
    await scraper.run()


def run_cli():
    """Run CLI parsing and execute scraper."""
    parser = argparse.ArgumentParser(description="Deutsche Bank Scraper")
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
