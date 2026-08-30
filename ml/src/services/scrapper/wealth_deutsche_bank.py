"""
Deutsche Wealth (wealth.db.com) Investing Insights Scraper
Using Crawlee Python with PlaywrightCrawler

Organic navigation — only START_URL is hardcoded:
  Step 1 → https://wealth.db.com/          : find & click "Insights" nav item
  Step 2 → /insights                        : find & click "Investing Insights"
  Step 3 → /insights/investing-insights     : collect the 3 sub-section links:
                                              - Economic Outlook
                                              - Investing Themes
                                              - Asset-class Insights
  Step 4 → each sub-section                 : collect all article/report links
  Step 5 → each article                     : find embedded PDF link,
                                              extract PDF text, save output

NOTE: The Economic Outlook section lives on www.deutschewealth.com — both
      wealth.db.com and deutschewealth.com are treated as the same site.

Time-window filtering via lookback_days.
Only articles whose published date falls within the window are scraped.
Articles with no detectable date are included (safe default).
"""

import argparse
import asyncio
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    ScrapeOutput,
    load_scraper_config,
)
from src.services.scrapper.date_filter import is_within_lookback, parse_date
from src.services.scrapper.pdf_scraper import PDFScraper
from src.services.scrapper.resilience import (
    build_playwright_retry_defaults,
    wait_for_any_selector,
)
from src.utils.logger import get_logger

# ── Constants ─────────────────────────────────────────────────────────────────
SOURCE_NAME = "wealth_deutsche_bank"
START_URL = "https://wealth.db.com"

# Both domains serve the same content
KNOWN_DOMAINS = {
    "wealth.db.com",
    "www.wealth.db.com",
    "deutschewealth.com",
    "www.deutschewealth.com",
}

logger = get_logger(__name__)

_pdf_scraper = PDFScraper()


def get_config():
    """Load scraper configuration."""
    return load_scraper_config(SOURCE_NAME)


# ── Helpers ───────────────────────────────────────────────────────────────────




def resolve_url(href: str, page_url: str) -> str:
    """Make href absolute. Relative paths are joined against the page origin."""
    if href.startswith("http"):
        return href
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(base, href)


def is_known_domain(url: str) -> bool:
    """Check if URL belongs to DW domains."""
    host = urlparse(url).netloc.lower()
    return host in KNOWN_DOMAINS or host.removeprefix("www.") in {
        d.removeprefix("www.") for d in KNOWN_DOMAINS
    }


# ── URL classification ────────────────────────────────────────────────────────


def _path(url: str) -> str:
    return urlparse(url).path.rstrip("/")


def _is_home(url: str) -> bool:
    p = _path(url)
    return is_known_domain(url) and p in ("", "/en", "/en/")


def _is_insights_hub(url: str) -> bool:
    p = _path(url)
    return (
        is_known_domain(url)
        and "/insights" in p
        and "/investing-insights" not in p
        and not _is_home(url)
    )


def _is_investing_insights_hub(url: str) -> bool:
    p = _path(url)
    return (
        is_known_domain(url)
        and "/investing-insights" in p
        and not _is_subsection_path(p)
        and not _is_article_path(p)
    )


_SUBSECTION_SLUGS = (
    "/economic-and-market-outlook",
    "/investing-themes",
    "/asset-class-insights",
)


def _is_subsection_path(path: str) -> bool:
    return any(
        path.endswith(s) or path.endswith(s + ".html") for s in _SUBSECTION_SLUGS
    )


def _is_subsection(url: str) -> bool:
    return is_known_domain(url) and _is_subsection_path(_path(url))


def _is_article_path(path: str) -> bool:
    """Article pages sit deeper than the subsection listing pages."""
    segs = [s for s in path.split("/") if s]
    in_ii = "investing-insights" in path
    deep = len(segs) >= 5
    not_listing = not _is_subsection_path(path)
    not_hub = not path.endswith("investing-insights") and not path.endswith(
        "investing-insights.html"
    )
    return in_ii and deep and not_listing and not_hub


def _is_article(url: str) -> bool:
    """Check if URL represents an article."""
    return is_known_domain(url) and _is_article_path(_path(url))


def _category_from_url(url: str) -> str:
    p = url.lower()
    if "economic-and-market-outlook" in p:
        return "Economic Outlook"
    if "investing-themes" in p:
        return "Investing Themes"
    if "asset-class-insights" in p:
        return "Asset-class Insights"
    return "Investing Insights"


# ── Overlay dismissal ─────────────────────────────────────────────────────────


async def dismiss_overlays(page) -> None:
    """Attempt a best-effort dismissal of cookie banners and popups."""
    overlays = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button[id*='accept']",
        "button[id*='cookie']",
        "button[aria-label*='Accept']",
        "button[class*='accept']",
        "button[class*='close']",
    ]
    for sel in overlays:
        try:
            # Check if it's visible first to avoid long timeouts
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2_000)
                logger.info("  [✓] Overlay dismissed")
                await asyncio.sleep(0.5)
                break
        except Exception:
            continue


# ── Scraper Class ─────────────────────────────────────────────────────────────


class WealthDesktopBankScraper:
    """Crawler class for Deutsche Wealth Investing Insights."""

    SOURCE_NAME = "wealth_deutsche_bank"

    def __init__(self, lookback_days: int, max_articles: int, output_file: str):
        self.lookback_days = lookback_days
        self.max_articles = max_articles
        self.output_file = output_file
        self.scraped_articles: list[Article] = []
        self.article_titles: dict[str, str] = {}
        self.article_dates: dict[str, str] = {}
        self.used_pdf_urls: set[str] = set()
        self.stats = {"total_found": 0, "total_within_window": 0}

    async def run(self):
        """Build and execute the crawler."""
        logger.info("=" * 60)
        logger.info("Deutsche Wealth — Investing Insights Scraper")
        logger.info("Entry      : %s", START_URL)
        logger.info("Out        : %s", self.output_file)
        logger.info("Time window: last %s day(s)", self.lookback_days)
        logger.info("=" * 60)

        # ── Isolate configuration to prevent asyncio.Lock event loop conflicts ─────
        config = Configuration(storage_dir=f"storage_{self.SOURCE_NAME}")

        retry_settings = build_playwright_retry_defaults(
            load_scraper_config(SOURCE_NAME)
        )
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
            request_handler_timeout=timedelta(seconds=180),
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
        await crawler.run([START_URL])

        self.save_results()

    async def universal_handler(self, ctx: PlaywrightCrawlingContext) -> None:
        """Route URLs based on classification."""
        url = ctx.request.url
        logger.info("Processing: %s", url)

        if not is_known_domain(url):
            logger.info("  [?] External domain — skipping")
            return

        await wait_for_any_selector(
            ctx.page,
            ["main", "article", "a[href*='/insights']"],
            timeout_ms=20000,
        )

        await dismiss_overlays(ctx.page)

        home = _is_home(url)
        ii_hub = _is_investing_insights_hub(url)
        subsec = _is_subsection(url)
        article = _is_article(url)
        insights = _is_insights_hub(url) and not ii_hub and not home

        logger.info(
            "  classify → home=%s insights=%s ii_hub=%s subsec=%s article=%s",
            home,
            insights,
            ii_hub,
            subsec,
            article,
        )

        if article:
            await self._handle_article_route(ctx)
        elif subsec:
            await self._handle_subsection_route(ctx)
        elif ii_hub:
            await self._handle_ii_hub_route(ctx)
        elif insights:
            await self._handle_insights_hub_route(ctx)
        elif home:
            await self._handle_home_route(ctx)
        else:
            logger.info("  [?] Unclassified URL — skipping")

    async def _handle_article_route(self, ctx: PlaywrightCrawlingContext):
        url = ctx.request.url
        logger.info("[STEP 5] Article: %s", url)
        meta = await ctx.page.evaluate(JS_EXTRACT_META)
        category = _category_from_url(url)

        for _ in range(3):
            await ctx.page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.7)

        clean_url = url.split("?")[0].split("#")[0]
        title = meta["title"] or self.article_titles.get(clean_url, "")
        date_str = meta["dateStr"] or self.article_dates.get(clean_url)
        art_date = parse_date(date_str)

        if art_date:
            logger.info("  [date] %s (from: %r)", art_date.date(), date_str)
        else:
            logger.info("  [date] None detected from DOM (dateStr=%r)", date_str)

        if not is_within_lookback(
            art_date.isoformat() if art_date else None, self.lookback_days
        ):
            logger.info("  [X] Outside window — skipping")
            return

        self.stats["total_within_window"] += 1
        content = await self._extract_content(ctx, meta)

        art_date = self._fallback_date(content, art_date)

        art = Article(
            source="wealth_deutsche_bank",
            url=url,
            title=title,
            content=content,
            summary=meta["summary"],
            metadata=ArticleMetadata(
                published_date=art_date.isoformat() if art_date else None,
                category=category,
            ),
        )

        logger.info("  [✓] Scraped: %s… (%s chars)", art.title[:60], len(art.content))
        self.scraped_articles.append(art)

    async def _extract_content(self, ctx, meta):
        pdf_links = meta.get("pdfLinks") or []
        content = ""
        if pdf_links:
            for pl in pdf_links:
                pdf_url = resolve_url(pl["href"], ctx.request.url)
                if pdf_url in self.used_pdf_urls:
                    logger.info(
                        "    [=] Shared PDF already used — falling back to body text: %s",
                        pdf_url,
                    )
                    continue
                result = await _pdf_scraper.scrape(pdf_url)
                if result.status == "success" and result.content:
                    content = result.content
                    self.used_pdf_urls.add(pdf_url)
                    logger.info("    [✓] PDF extracted %s chars", len(content))
                    break
        if not content:
            if pdf_links:
                logger.warning("    [!] PDF downloads failed — using body text")
            else:
                logger.warning("    [!] No PDF link — using body text")
            content = meta["body"]
        return content

    def _fallback_date(self, content, current_date):
        if current_date or not content:
            return current_date
        months_pattern = (
            "January|February|March|April|May|June|"
            "July|August|September|October|November|December"
        )
        date_re = re.compile(
            rf"(?:(\d{{1,2}})\s+)?({months_pattern})\s+(\d{{4}})"
            rf"|({months_pattern})\s+(\d{{1,2}}),?\s+(\d{{4}})",
            re.IGNORECASE,
        )
        match = date_re.search(content[:5000])
        if match:
            try:
                if match.group(2):
                    day = int(match.group(1)) if match.group(1) else 1
                    month, year = match.group(2), int(match.group(3))
                else:
                    day, month, year = (
                        int(match.group(5)),
                        match.group(4),
                        int(match.group(6)),
                    )
                new_date = datetime.strptime(f"{day} {month} {year}", "%d %B %Y")
                logger.info(
                    "  [date-fallback] %s (from content regex)", new_date.date()
                )
                return new_date
            except ValueError:
                pass
        return current_date

    async def _handle_subsection_route(self, ctx: PlaywrightCrawlingContext):
        url = ctx.request.url
        category = _category_from_url(url)
        logger.info("[STEP 4] Sub-section '%s': %s", category, url)

        for _ in range(6):
            await ctx.page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)

        links = await ctx.page.evaluate(JS_EXTRACT_LINKS, url)
        logger.info("  [✓] Found %s candidate link(s)", len(links))
        self.stats["total_found"] += len(links)

        to_queue = []
        for lnk in links:
            clean = lnk["href"].split("?")[0].split("#")[0]
            if clean.lower().endswith(".pdf"):
                continue
            if lnk["text"]:
                self.article_titles[clean] = lnk["text"]

            p_date = parse_date(lnk.get("dateStr"))
            if p_date:
                if not is_within_lookback(p_date.isoformat(), self.lookback_days):
                    continue
                self.article_dates[clean] = p_date.isoformat()

            logger.info("    [+] Queuing: %s", lnk["text"][:55])
            to_queue.append(clean)

        if to_queue:
            await ctx.add_requests(to_queue)

    async def _handle_ii_hub_route(self, ctx: PlaywrightCrawlingContext):
        logger.info("[STEP 3] Investing Insights hub → collecting sub-section links")
        await asyncio.sleep(1)
        sub_links = await ctx.page.evaluate(JS_EXTRACT_SUBSECTIONS)

        if not sub_links:
            logger.warning("  [!] No sub-section links found — using fallbacks")
            base = "https://www.deutschewealth.com"
            sub_links = [
                {
                    "href": f"{base}/en/insights/investing-insights/economic-and-market-outlook.html",
                    "text": "EO",
                },
                {
                    "href": "https://wealth.db.com/en/insights/investing-insights/investing-themes.html",
                    "text": "IT",
                },
                {
                    "href": "https://wealth.db.com/en/insights/investing-insights/asset-class-insights.html",
                    "text": "AI",
                },
            ]

        seen = set()
        queue = []
        for lnk in sub_links:
            href = resolve_url(lnk["href"], ctx.request.url)
            if href not in seen:
                seen.add(href)
                logger.info("  [→] Sub-section: %s → %s", lnk["text"], href)
                queue.append(href)
        if queue:
            await ctx.add_requests(queue)

    async def _handle_insights_hub_route(self, ctx: PlaywrightCrawlingContext):
        logger.info("[STEP 2] Insights page → looking for 'Investing Insights'")
        try:
            sel = "a[href*='investing-insights'], a:has-text('Investing Insights')"
            ii_link = ctx.page.locator(sel).first
            if await ii_link.count() > 0:
                href = await ii_link.get_attribute("href")
                full = resolve_url(href, ctx.request.url)
                logger.info("  [✓] Found 'Investing Insights': %s", full)
                await ctx.add_requests([full])
                return
        except (AttributeError, TypeError, TimeoutError) as exc:
            logger.error("  [!] Link not found: %s", exc)
        await ctx.add_requests(
            ["https://wealth.db.com/en/insights/investing-insights.html"]
        )

    async def _handle_home_route(self, ctx: PlaywrightCrawlingContext):
        logger.info("[STEP 1] Homepage → looking for 'Insights' nav item")
        try:
            sel = "a[href*='/insights']:not([href*='investing']):not([href*='asset']), a:has-text('Insights')"
            link = ctx.page.locator(sel).first
            if await link.count() > 0:
                href = await link.get_attribute("href")
                full = resolve_url(href, ctx.request.url)
                logger.info("  [✓] Found Insights nav: %s", full)
                try:
                    await link.click(timeout=5_000)
                    await asyncio.sleep(1)
                    await ctx.page.goto(full, wait_until="load", timeout=45_000)
                except (AttributeError, TypeError, TimeoutError):
                    await ctx.page.goto(full, wait_until="load", timeout=45_000)
                await ctx.add_requests([ctx.page.url])
                return
        except (AttributeError, TypeError, TimeoutError) as exc:
            logger.error("  [!] Insights link not found: %s", exc)
        await ctx.add_requests(["https://wealth.db.com/en/insights.html"])

    def save_results(self) -> None:
        """Save captured articles to JSON."""
        if not self.scraped_articles:
            logger.warning("Nothing to save.")
            return
        output = ScrapeOutput(
            source=SOURCE_NAME,
            lookback_days=self.lookback_days,
            total_found=self.stats["total_found"],
            total_within_window=self.stats["total_within_window"],
            total_scraped=len(self.scraped_articles),
            articles=self.scraped_articles,
        )
        output.save(self.output_file)
        logger.info("JSON saved to %s", self.output_file)


# ── JS Scripts ────────────────────────────────────────────────────────────────

JS_EXTRACT_META = """() => {
    let title = '';
    for (const sel of ['h1', '.article-title', '.headline', '[class*="headline"]', '[class*="title"]', 'h2']) {
        const el = document.querySelector(sel);
        if (el?.innerText?.trim()) { title = el.innerText.trim(); break; }
    }
    title = title || document.title;

    let dateStr = null;
    const timeEl = document.querySelector('time');
    if (timeEl) { dateStr = timeEl.getAttribute('datetime') || timeEl.innerText.trim(); }
    if (!dateStr) {
        for (const sel of [
            '[class*="date"]', '.article-date', '.post-date', '.meta-date', 'span.date',
            '[data-date]', '.date-published', '.entry-date'
        ]) {
            const el = document.querySelector(sel);
            if (el?.innerText?.trim()) { dateStr = el.innerText.trim(); break; }
            if (el?.getAttribute('data-date')) { dateStr = el.getAttribute('data-date'); break; }
        }
    }
    if (!dateStr) {
        document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
            try {
                const d = JSON.parse(s.textContent);
                if (d.datePublished) dateStr = d.datePublished;
            } catch(_) {}
        });
    }

    const metaDesc = document.querySelector('meta[name="description"]');
    const summary = metaDesc?.getAttribute('content') || '';
    const bodyEls = document.querySelectorAll('article p, .article-body p, .content p, p');
    const body = Array.from(bodyEls).map(p => p.innerText.trim()).filter(t => t.length > 30).join('\\n\\n');

    const pdfLinks = Array.from(document.querySelectorAll('a[href]'))
        .map(a => ({ href: a.href, text: (a.innerText || a.title || '').trim() }))
        .filter(l => l.href.toLowerCase().endsWith('.pdf') || /\\bpdf\\b/i.test(l.text));

    return { title, dateStr, summary, body, pdfLinks };
}"""

JS_EXTRACT_LINKS = """(pageUrl) => {
    const seen = new Set();
    const base = new URL(pageUrl);
    const results = [];
    const knownHosts = new Set(['wealth.db.com', 'www.wealth.db.com', 'deutschewealth.com', 'www.deutschewealth.com']);

    document.querySelectorAll('a[href]').forEach(a => {
        const href = a.href;
        let u;
        try { u = new URL(href); } catch(_) { return; }
        if (!knownHosts.has(u.hostname.toLowerCase())) return;
        if (!u.pathname.includes('/insights/')) return;
        if (u.pathname.split('/').length <= base.pathname.split('/').length) return;
        if (seen.has(href)) return;
        seen.add(href);

        const parent = a.closest('article') || a.closest('li') || a.closest('.card') || a.parentElement;
        let dateStr = null;
        const timeEl = parent?.querySelector('time');
        if (timeEl) { dateStr = timeEl.getAttribute('datetime') || timeEl.innerText.trim(); }
        const text = (a.innerText || a.title || '').replace(/\\s+/g, ' ').trim();
        results.push({ href, text, dateStr });
    });
    return results;
}"""

JS_EXTRACT_SUBSECTIONS = """() => {
    const items = document.querySelectorAll('.mobile-sublink-ul li a, ul.mobile-sublink-ul a');
    if (items.length) {
        return Array.from(items).map(a => ({ href: a.href, text: (a.innerText || '').trim() }));
    }
    return Array.from(document.querySelectorAll('a[href]'))
        .filter(a => a.href.includes('economic-and-market-outlook') || a.href.includes('investing-themes') || a.href.includes('asset-class-insights'))
        .map(a => ({ href: a.href, text: (a.innerText || '').trim() }));
}"""


async def main(
    lookback_days: int | None = None,
    max_articles: int = 100,
    output_file: str | None = None,
) -> None:
    """Async main function."""
    cfg = get_config()
    final_output_file = output_file or cfg["output_file"]
    effective_lookback = (
        lookback_days if lookback_days is not None else cfg.get("lookback_days", 1) or 1
    )
    final_max_art = max_articles or cfg["max_articles"]

    scraper = WealthDesktopBankScraper(
        effective_lookback, final_max_art, final_output_file
    )
    await scraper.run()


def run_cli():
    """Run CLI to parse arguments and execute the scraper."""
    parser = argparse.ArgumentParser(description="Deutsche Wealth Scraper")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--max-articles", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )

    scraper_cfg_global = get_config()
    lookback_global = (
        args.lookback_days
        if args.lookback_days is not None
        else scraper_cfg_global["lookback_days"]
    )
    max_art_global = (
        args.max_articles
        if args.max_articles is not None
        else scraper_cfg_global["max_articles"]
    )
    out_file_global = scraper_cfg_global["output_file"]

    asyncio.run(
        main(
            lookback_days=lookback_global,
            max_articles=max_art_global,
            output_file=out_file_global,
        )
    )


if __name__ == "__main__":
    run_cli()
