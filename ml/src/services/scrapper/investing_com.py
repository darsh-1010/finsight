"""Investing.com Stock Market News Scraper.

Using Crawlee Python with PlaywrightCrawler and stealthed Camoufox Firefox browser.

Organic navigation — only START_URL is hardcoded:
  Step 1 → investing.com  : find "News" in navbar
  Step 2 → News page      : find "Stock Markets" section and navigate to it
  Step 3 → Stock Markets  : collect article links published within TIME_WINDOW_HOURS
  Step 4 → each article   : scrape full text, extract published_date, save to output folder
"""

import argparse
import asyncio
import logging
import os
import random
import re
import shutil
from datetime import timedelta

from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    ScrapeOutput,
    load_scraper_config,
)
from src.services.scrapper.camoufox_plugin import build_camoufox_pool
from src.services.scrapper.date_filter import is_within_lookback, parse_date
from src.services.scrapper.resilience import (
    build_playwright_retry_defaults,
    detect_bot_block,
    wait_for_any_selector,
    wait_for_post_action_settle,
)
from src.utils.logger import get_logger

# ── Configuration ─────────────────────────────────────────────────────────────
SOURCE_NAME = "investing_com"
START_URL = "https://www.investing.com"

logger = get_logger(__name__)


def get_config():
    """Load scraper config."""
    return load_scraper_config(SOURCE_NAME)


# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_filename(text: str, max_len: int = 80) -> str:
    """Generate a safe filename from article title."""
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len] or "untitled"


def save_results(
    scraped_articles: list,
    stats: dict,
    lookback_days_val: float,
    output_file: str,
) -> None:
    """Save scraped results to JSON file."""
    if not scraped_articles:
        logger.warning("Nothing to save.")
        return

    output = ScrapeOutput(
        source=SOURCE_NAME,
        lookback_days=int(lookback_days_val),
        total_found=stats["total_found"],
        total_within_window=stats["total_within_window"],
        total_scraped=len(scraped_articles),
        articles=scraped_articles,
    )

    output.save(output_file)
    logger.info("JSON saved to %s", output_file)


async def dismiss_overlays(page) -> None:
    """Close cookie banners and modals that block navigation."""
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
            # Check if it's visible first to avoid long timeouts
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2_000)
                await wait_for_post_action_settle(page, [], timeout_ms=1500)
                break
        except Exception:  # pylint: disable=broad-exception-caught
            continue


# ── URL classifier ────────────────────────────────────────────────────────────
def _is_article_url(url: str) -> bool:
    """Classify if the given URL is an article page."""
    path = url.split("investing.com")[-1].split("?")[0].split("#")[0]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 3 or parts[0] != "news":
        return False
    return bool(re.search(r"-\d{5,}", parts[-1]) or re.search(r"\d{5,}", parts[-1]))


# ── Scraper Class ─────────────────────────────────────────────────────────────
class InvestingComScraper:
    """Scrapes stock market news from Investing.com with anti-bot resilience."""

    SOURCE_NAME = "investing_com"
    START_URL = "https://www.investing.com"

    def __init__(
        self,
        lookback_days: int | None = None,
        max_articles: int | None = None,
        output_file: str | None = None,
    ):
        cfg = load_scraper_config(self.SOURCE_NAME)
        self.config = cfg
        self.lookback_days = (
            lookback_days if lookback_days is not None else cfg["lookback_days"]
        )
        self.max_articles = max_articles or cfg["max_articles"]
        self.output_file = output_file or cfg["output_file"]

        self._articles: list[Article] = []
        self._article_titles: dict[str, str] = {}
        self._article_dates: dict[str, str] = {}  # clean_url → ISO date string
        self._stats = {"total_found": 0, "total_within_window": 0}

    async def _handle_cloudflare(self, page, url: str) -> None:
        """Detect and handle Cloudflare challenge pages."""
        for attempt in range(1, 4):
            page_html = await page.content()
            if "challenge.cloudflare.com" in page.url or detect_bot_block(page_html):
                logger.warning(
                    "[CLOUDFLARE_CHALLENGE] Cloudflare challenge page detected on attempt %d/3. "
                    "Waiting 15 seconds for challenge completion...",
                    attempt,
                )
                await asyncio.sleep(15)
            else:
                break
        else:
            page_html = await page.content()
            if "challenge.cloudflare.com" in page.url or detect_bot_block(page_html):
                raise RuntimeError(f"[ANTI_BOT_BLOCK] Blocked by Cloudflare on {url}")

    async def _ensure_hydration(self, page, url: str) -> None:
        """Ensure the target page elements have hydrated."""
        page_ready = await wait_for_any_selector(
            page,
            ["main", "article", "nav", "a[href*='/news']"],
            timeout_ms=45000,
            source=self.SOURCE_NAME,
        )

        if not page_ready:
            logger.warning(
                "[DOM_TIMEOUT] Selectors did not hydrate on %s. Trying to proceed.",
                url,
            )
        else:
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    async def _handle_article(self, ctx: PlaywrightCrawlingContext) -> None:
        """Scrape full text content and metadata from an individual article."""
        page = ctx.page
        url = ctx.request.url
        logger.info("[STEP 4] Article: %s", url)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.6)

        meta = await page.evaluate("""() => {
            let title = '';
            for (const sel of [
                'h1.articleHeader', 'h1[class*="title"]', 'h1[class*="heading"]',
                '.article_header h1', 'h1',
            ]) {
                const el = document.querySelector(sel);
                if (el?.innerText?.trim()) { title = el.innerText.trim(); break; }
            }
            title = title || document.title;

            let author = null;
            for (const sel of [
                '[class*="author"] [itemprop="name"]',
                '[class*="authorName"]', '[class*="author-name"]',
                '[rel="author"]', '.articleDetails span',
                '[class*="author"]',
            ]) {
                const el = document.querySelector(sel);
                if (el?.innerText?.trim()) { author = el.innerText.trim(); break; }
            }

            let dateStr = null;
            const publishedDiv = document.querySelector('div.flex.flex-row.items-center');
            if (publishedDiv) {
                const spans = Array.from(publishedDiv.querySelectorAll('span'));
                const pubSpan = spans.find(s => s.textContent.trim().startsWith('Published'));
                if (pubSpan) dateStr = pubSpan.textContent.trim();
            }
            if (!dateStr) {
                const spans = Array.from(document.querySelectorAll('span'));
                const pubSpan = spans.find(s => s.textContent.trim().startsWith('Published'));
                if (pubSpan) dateStr = pubSpan.textContent.trim();
            }
            if (!dateStr) {
                for (const sel of ['time[datetime]', 'time']) {
                    const el = document.querySelector(sel);
                    if (el) {
                        dateStr = el.getAttribute('datetime') || el.innerText.trim();
                        if (dateStr) break;
                    }
                }
            }
            if (!dateStr) {
                for (const sel of [
                    '[class*="publish"]', '[class*="date"]', '[class*="Date"]',
                    '[class*="pubDate"]', '.articleDetails', '.article-details',
                    '[data-test="article-header-date"]',
                    '.article_header .date', 'span[class*="date"]',
                    '[class*="article-meta"]', '[class*="articleMeta"]',
                    '[class*="timestamp"]', '[class*="Timestamp"]',
                    '[data-timestamp]', '[data-article-date]',
                ]) {
                    const el = document.querySelector(sel);
                    if (el?.getAttribute('data-timestamp')) { dateStr = el.getAttribute('data-timestamp'); break; }
                    if (el?.getAttribute('datetime')) { dateStr = el.getAttribute('datetime'); break; }
                    if (el?.innerText?.trim()) { dateStr = el.innerText.trim(); break; }
                }
            }
            if (!dateStr) {
                document.querySelectorAll('script[type="application/ld+json"]')
                    .forEach(s => {
                        try {
                            const d = JSON.parse(s.textContent);
                            if (d.datePublished) dateStr = d.datePublished;
                            if (!dateStr && d['@graph']) {
                                d['@graph'].forEach(item => {
                                    if (item.datePublished) dateStr = item.datePublished;
                                });
                            }
                        } catch(_) {}
                    });
            }
            if (!dateStr) {
                for (const name of [
                    'article:published_time', 'datePublished',
                    'DC.date', 'date', 'pubdate', 'publish_date',
                ]) {
                    const el = document.querySelector(
                        `meta[property="${name}"], meta[name="${name}"]`
                    );
                    if (el) { dateStr = el.getAttribute('content'); break; }
                }
            }
            if (!dateStr) {
                const el = document.querySelector('[data-timestamp]');
                if (el) dateStr = el.getAttribute('data-timestamp');
            }

            const metaDesc = document.querySelector('meta[name="description"]');
            const summary  = metaDesc?.getAttribute('content') || '';

            const body = Array.from(document.querySelectorAll(
                '.article_WYSIWYG p, .articlePage p, article p, .WYSIWYG p, main p, p'
            ))
                .map(p => p.innerText.trim())
                .filter(t => t.length > 30)
                .join('\\n\\n');

            return { title, author, dateStr, summary, body };
        }""")

        clean_url = url.split("?")[0].split("#")[0]
        if (
            not meta["title"] or "Investing.com" in meta["title"]
        ) and clean_url in self._article_titles:
            meta["title"] = self._article_titles[clean_url]

        date_str = meta.get("dateStr") or self._article_dates.get(clean_url)
        pub_date = parse_date(date_str)

        if pub_date:
            logger.info("  [date] %s (from: %r)", pub_date.isoformat(), date_str)
        else:
            logger.info("  [date] None detected (dateStr=%r)", date_str)

        lookback_days_float = float(self.lookback_days)
        if not is_within_lookback(
            pub_date.isoformat() if pub_date else None, lookback_days_float
        ):
            logger.info(
                "  [X] Outside %dh window — skipping", int(self.lookback_days * 24)
            )
            return

        self._stats["total_within_window"] += 1

        article = Article(
            source=self.SOURCE_NAME,
            url=url,
            title=meta["title"],
            content=meta["body"],
            summary=meta["summary"],
            metadata=ArticleMetadata(
                published_date=pub_date.isoformat() if pub_date else None,
                author=meta.get("author"),
                category="Stock Markets",
            ),
        )
        self._articles.append(article)
        logger.info(
            "  [✓] Scraped: %s… (%d chars)", article.title[:60], len(article.content)
        )

    async def _handle_stock_markets(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle the Stock Markets listing page, collecting target links."""
        page = ctx.page
        lookback_hours = int(self.lookback_days * 24)
        logger.info(
            "[STEP 3] Stock Markets listing → collecting links from last %dh",
            lookback_hours,
        )

        for i in range(10):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await asyncio.sleep(1)

            try:
                show_more = page.locator(
                    "a:has-text('Show More'), button:has-text('Show More'), "
                    "a:has-text('Load More'), .searchMaxResults + div a"
                ).first
                if await show_more.is_visible():
                    logger.info("    [*] Clicking 'Show More' (step %d)", i + 1)
                    await show_more.click()
                    await asyncio.sleep(2)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        links = await page.evaluate("""() => {
            const seen = new Set();
            const results = [];
            const selectors = [
                'article', '[data-test="article-item"]',
                '.js-article-item', '[class*="articleItem"]',
                '.common-article-item',
            ];
            let items = [];
            for (const sel of selectors) {
                items = Array.from(document.querySelectorAll(sel));
                if (items.length > 0) break;
            }
            if (items.length === 0) {
                items = Array.from(document.querySelectorAll(
                    'main a[href*="/news/"], section a[href*="/news/"]'
                )).map(a => a.closest('li, div, article') || a);
            }
            items.forEach(item => {
                const a = item.querySelector('a[href*="/news/"]') || item.closest('a');
                if (!a) return;
                const href = a.href;
                if (!href || seen.has(href)) return;
                seen.add(href);

                const text = (a.innerText || a.title || '').replace(/\\s+/g, ' ').trim();

                let dateStr = null;
                let tsEl = item.querySelector('[data-timestamp]');
                if (tsEl) { dateStr = tsEl.getAttribute('data-timestamp'); }
                if (!dateStr) {
                    const timeEl = item.querySelector('time');
                    if (timeEl) {
                        dateStr = timeEl.getAttribute('datetime') || timeEl.innerText.trim();
                    }
                }
                if (!dateStr) {
                    for (const sel of [
                        '[class*="date"]', '[class*="Date"]', '[class*="timestamp"]',
                        '[class*="pubDate"]', 'span.date',
                    ]) {
                        const el = item.querySelector(sel);
                        if (el?.innerText?.trim()) { dateStr = el.innerText.trim(); break; }
                    }
                }
                results.push({ href, text, dateStr });
            });
            return results;
        }""")

        logger.info("  [✓] Found %d candidate link(s)", len(links))
        self._stats["total_found"] += len(links)

        to_queue = []
        for lnk in links:
            clean = lnk["href"].split("?")[0].split("#")[0]
            if not _is_article_url(clean):
                continue

            if lnk["text"]:
                self._article_titles[clean] = lnk["text"]

            pub = parse_date(lnk.get("dateStr"))
            if pub:
                self._article_dates[clean] = pub.isoformat()
                buffered_date = pub + timedelta(hours=12)
                if not is_within_lookback(
                    buffered_date.isoformat(), float(self.lookback_days)
                ):
                    continue
                logger.info(
                    "    [+] Queuing (%s): %s", pub.strftime("%H:%M"), lnk["text"][:55]
                )
            else:
                logger.info(
                    "    [?] No date found in item, will check inside article: %s",
                    lnk["text"][:55],
                )

            to_queue.append(clean)

        if to_queue:
            await ctx.add_requests(to_queue)
        logger.info("  [✓] Queued %d article(s) for scraping", len(to_queue))

    async def _handle_news_hub(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle the News Hub page, directing the crawl to Stock Markets."""
        page = ctx.page
        logger.info("[STEP 2] News hub → finding 'Stock Markets' link")

        try:
            sm_link = page.locator("a[href*='stock-market-news']").first
            if await sm_link.count() > 0:
                href = await sm_link.get_attribute("href")
                full = href if href.startswith("http") else f"{self.START_URL}{href}"
                logger.info("  [✓] Stock Markets link: %s", full)
                await ctx.add_requests([full])
                return
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.info("  [!] Direct link search failed: %s", e)

        logger.info("  [!] Falling back to direct Stock Markets URL")
        await ctx.add_requests(["https://www.investing.com/news/stock-market-news"])

    async def _handle_homepage(self, ctx: PlaywrightCrawlingContext) -> None:
        """Handle the main homepage, locating the navigation to Stock Markets."""
        page = ctx.page
        logger.info("[STEP 1] Homepage → finding 'News' navbar link")

        try:
            news_item = page.locator(
                "a.navbar_nav_item_link__hDYJW:has-text('News'), "
                "a[href='/news/']:has-text('News'), "
                "a[href*='/news']:has(span:text('News'))"
            ).first
            if await news_item.count() > 0:
                await news_item.hover()
                await asyncio.sleep(0.8)

                try:
                    sm = page.locator(
                        "a.navbar_multi_list_link__B8IEy:has-text('Stock Markets'), "
                        "a[href*='stock-market-news']"
                    ).first
                    if await sm.count() > 0:
                        href = await sm.get_attribute("href")
                        full = (
                            href
                            if href.startswith("http")
                            else f"{self.START_URL}{href}"
                        )
                        logger.info("  [✓] Found 'Stock Markets' in dropdown: %s", full)
                        await ctx.add_requests([full])
                        return
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                href = await news_item.get_attribute("href")
                if href:
                    full = (
                        href if href.startswith("http") else f"{self.START_URL}{href}"
                    )
                    logger.info("  [✓] Navigating to News hub: %s", full)
                    await ctx.add_requests([full])
                    return

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.info("  [!] Navbar hover failed: %s", e)

        logger.info("  [!] Falling back to direct news/stock-market-news URL")
        await ctx.add_requests(["https://www.investing.com/news/stock-market-news"])

    async def universal_handler(self, ctx: PlaywrightCrawlingContext) -> None:
        """Universal route classifier and orchestrator."""
        page = ctx.page
        url = ctx.request.url
        logger.info("Processing: %s", url)

        await self._handle_cloudflare(page, url)
        await self._ensure_hydration(page, url)
        await dismiss_overlays(page)

        is_homepage = url.strip("/").rstrip("/") in (
            self.START_URL.rstrip("/"),
            self.START_URL.rstrip("/") + "/en",
        )
        is_news_hub = "/news/" == url.split("investing.com")[-1].split("?")[
            0
        ] or url.rstrip("/").endswith("/news")
        is_stock_markets = "/news/stock-market-news" in url and not _is_article_url(url)
        is_article = _is_article_url(url)

        if is_article:
            await self._handle_article(ctx)
        elif is_stock_markets:
            await self._handle_stock_markets(ctx)
        elif is_news_hub:
            await self._handle_news_hub(ctx)
        elif is_homepage:
            await self._handle_homepage(ctx)
        else:
            logger.info("  [?] Unrecognised route — skipping %s", url)

    async def scrape_async(self) -> None:
        """Crawlee-based async pipeline."""
        self._articles = []
        self._article_titles = {}
        self._article_dates = {}
        self._stats = {"total_found": 0, "total_within_window": 0}

        # Purge stale Crawlee storage to avoid warnings
        storage_dir = os.path.join(os.getcwd(), f"storage_{self.SOURCE_NAME}")
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir, ignore_errors=True)

        config = Configuration(storage_dir=storage_dir)
        retry_settings = build_playwright_retry_defaults(self.config)

        # Always use the shared custom CamoufoxPlugin BrowserPool for stealth and Cloudflare bypass
        browser_pool = build_camoufox_pool()

        crawler = PlaywrightCrawler(
            configuration=config,
            browser_pool=browser_pool,
            max_requests_per_crawl=self.max_articles,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1,
                max_concurrency=1,  # Stay at 1 — anti-bot sensitivity on investing.com
                desired_concurrency=1,
            ),
            navigation_timeout=timedelta(seconds=90),
            request_handler_timeout=timedelta(seconds=120),
            **retry_settings,
        )

        @crawler.pre_navigation_hook
        async def setup_page(ctx: PlaywrightCrawlingContext) -> None:
            ctx.page.set_default_navigation_timeout(90_000)
            try:
                ctx.goto_options["wait_until"] = "domcontentloaded"
            except (AttributeError, TypeError):
                pass
            # Randomized delay to appear organic
            await asyncio.sleep(random.uniform(1.0, 3.0))

        # Register our universal handler
        crawler.router.default_handler(self.universal_handler)

        logger.info("=" * 60)
        logger.info("Investing.com — Stock Market News Scraper")
        logger.info("Entry      : %s", self.START_URL)
        logger.info("Time window: last %d hour(s)", int(self.lookback_days * 24))
        logger.info("Output     : %s", self.output_file)
        logger.info("=" * 60)

        await crawler.run([self.START_URL])

        logger.info("\n%s", "=" * 60)
        logger.info("Done. Articles scraped: %d", len(self._articles))
        logger.info(
            "      Within %dd window: %d",
            self.lookback_days,
            self._stats["total_within_window"],
        )
        logger.info("=" * 60)

        save_results(
            self._articles, self._stats, float(self.lookback_days), self.output_file
        )


async def main(
    lookback_days: int, max_articles: int, output_file: str | None = None
) -> None:
    """Entry point coroutine for scheduler compatibility."""
    scraper = InvestingComScraper(
        lookback_days=lookback_days,
        max_articles=max_articles,
        output_file=output_file,
    )
    await scraper.scrape_async()


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Investing.com Stock Market News Scraper"
    )
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
    lookback_days_input = (
        args.lookback_days
        if args.lookback_days is not None
        else scraper_cfg_main["lookback_days"]
    )
    max_art_input = (
        args.max_articles
        if args.max_articles is not None
        else scraper_cfg_main["max_articles"]
    )
    OUT_FILE = scraper_cfg_main["output_file"]
    asyncio.run(
        main(
            lookback_days=lookback_days_input,
            max_articles=max_art_input,
            output_file=OUT_FILE,
        )
    )
