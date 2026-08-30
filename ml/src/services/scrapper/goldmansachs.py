"""
Goldman Sachs Outlooks Scraper
Using Crawlee Python with PlaywrightCrawler

Organic navigation — only START_URL is hardcoded:
  Step 1 → goldmansachs.com     : find & click "Explore Insights" / "Insights"
  Step 2 → /insights             : find & click "Outlooks" / "2026 Outlooks"
  Step 3 → /insights/outlooks/…  : collect all outlook article links
  Step 4 → each article          : scrape full text, save to output folder
"""

import argparse
import asyncio
import logging
from datetime import timedelta

from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (
    Article,
    ArticleMetadata,
    load_scraper_config,
)
from src.services.scrapper.camoufox_plugin import build_camoufox_pool
from src.services.scrapper.date_filter import is_within_lookback, parse_date
from src.services.scrapper.resilience import (
    SCRAPER_TRY_EXCEPTIONS,
    build_playwright_retry_defaults,
    detect_bot_block,
    wait_for_any_selector,
)
from src.services.scrapper.utils import dismiss_overlays, save_results
from src.utils.logger import get_logger

# ── ONLY hardcoded URL ───────────────────────────────────────────────────────
SOURCE_NAME = "goldmansachs"
START_URL = "https://www.goldmansachs.com/"

logger = get_logger(__name__)


def get_config():
    return load_scraper_config(SOURCE_NAME)


# ── Helpers ──────────────────────────────────────────────────────────────────



async def find_link_and_navigate(page, keywords: list[str], label: str) -> str | None:
    """
    Scan all <a> tags on the current page for one whose visible text contains
    any keyword (case-insensitive). Navigate to it and return the resolved URL.
    Returns None if nothing matched.
    """
    await page.wait_for_load_state("networkidle", timeout=30_000)
    await dismiss_overlays(page)

    # Light scroll to expose sticky-nav / lazy items
    await page.evaluate("window.scrollBy(0, 400)")
    await asyncio.sleep(1)

    all_links = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href]')).map(a => ({
            text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim(),
            href: a.href,
        })).filter(a => a.text && a.href.startsWith('http'));
    }""")

    for kw in keywords:
        kw_lower = kw.lower()
        for link in all_links:
            if kw_lower in link["text"].lower():
                logger.info(
                    f"  [✓] Matched '{kw}' → '{link['text']}'  ({link['href']})"
                )
                await page.goto(link["href"], wait_until="load", timeout=45_000)
                return page.url

    logger.info(f"  [!] None of {keywords} found on '{label}'")
    return None


# ── Crawler definition ────────────────────────────────────────────────────────


async def _handle_article(page, url: str, state: dict) -> None:
    logger.info(f"[STEP 4] Article Discovery: {url}")
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(0.5)

    scraped_data = await page.evaluate(r"""() => {
        let title = '';
        for (const sel of ['h1','[class*="headline"]','[class*="title"]']) {
            const el = document.querySelector(sel);
            if (el?.innerText?.trim()) { title = el.innerText.trim(); break; }
        }
        title = title || document.title;

        const body = Array.from(document.querySelectorAll('p'))
            .map(p => p.innerText.trim())
            .filter(t => t.length > 25)
            .join('\n\n');

        let dateStr = null;
        const timeEl = document.querySelector('time');
        if (timeEl) {
            dateStr = timeEl.getAttribute('datetime') || timeEl.innerText.trim();
        }
        if (!dateStr) {
            for (const sel of [
                '[class*="date"]', '[class*="publish"]', '[class*="Date"]',
                '.article-date', '.post-date', '.meta-date',
                '.publication-date', 'span.date', '[data-date]',
            ]) {
                const el = document.querySelector(sel);
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
                'article:published_time', 'datePublished', 'DC.date', 'date',
                'pubdate', 'publish_date',
            ]) {
                const el = document.querySelector(
                    `meta[property="${name}"], meta[name="${name}"]`
                );
                if (el) { dateStr = el.getAttribute('content'); break; }
            }
        }

        return { title, body, dateStr };
    }""")

    if (
        not scraped_data["title"] or "Goldman Sachs" in scraped_data["title"]
    ) and url in state["article_titles"]:
        scraped_data["title"] = state["article_titles"][url]

    date_str = scraped_data.get("dateStr")
    published_date = parse_date(date_str)

    if published_date:
        logger.info(f"  [date] {published_date.date()} (from: {date_str!r})")
        if not is_within_lookback(published_date.isoformat(), state["lookback_days"]):
            logger.info(
                f"  [X] Outside {state['lookback_days']}d window — skipping {url}"
            )
            return
    else:
        logger.info(f"  [date] None detected (dateStr={date_str!r})")

    article = Article(
        source="goldmansachs",
        url=url,
        title=scraped_data["title"],
        content=scraped_data["body"],
        summary=scraped_data.get("summary", ""),
        metadata=ArticleMetadata(
            published_date=published_date.isoformat() if published_date else None,
            category="Outlooks",
        ),
    )

    logger.info(
        f"  [✓] Scraped: {article.title[:50]}... ({len(article.content)} chars)"
    )
    state["scraped_outlooks"].append(article)
    state["stats"]["total_within_window"] += 1


async def _handle_outlooks_list(
    ctx: PlaywrightCrawlingContext,
    url: str,
    article_titles: dict[str, str],
    stats: dict,
) -> None:
    logger.info("[STEP 3] Outlooks listing → collecting article links")
    for _ in range(5):
        await ctx.page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(1)

    links = list(
        await ctx.page.evaluate(
            r"""currentUrl => {
        const seen = new Set();
        return Array.from(document.querySelectorAll('a[href]'))
            .map(a => ({
                href: a.href,
                text: (a.innerText || '').replace(/\s+/g, ' ').trim(),
            }))
            .filter(({ href }) => {
                return href.startsWith('https://www.goldmansachs.com') &&
                        href.includes('/insights/') &&
                        href !== currentUrl &&
                        !href.match(/\/insights\/?$/) &&
                        !href.includes('/outlooks/2026-outlooks') &&
                        !seen.has(href) && seen.add(href);
            });
    }""",
            url,
        )
    )

    logger.info(f"  [✓] Found {len(links)} article link(s)")
    stats["total_found"] += len(links)

    hrefs = []
    for i, link in enumerate(links, 1):
        clean_url = link["href"].split("#")[0].split("?")[0]
        article_titles[clean_url] = link["text"]
        hrefs.append(link["href"])
        logger.debug(f"{i:2d}. {link['text']} -> {clean_url}")

    if hrefs:
        await ctx.add_requests(hrefs)


async def _handle_insights_hub(ctx: PlaywrightCrawlingContext) -> None:
    logger.info("[STEP 2] Insights hub → looking for Outlooks link")
    try:
        more_plus = ctx.page.locator(
            "a:has-text('More +'), a.nav-link:has-text('More')"
        ).first
        if await more_plus.is_visible(timeout=5000):
            await more_plus.click()
            await asyncio.sleep(2)
    except SCRAPER_TRY_EXCEPTIONS:
        pass

    selector = "a[href*='/insights/outlooks/'], a:has-text('Outlooks')"
    try:
        outlooks_link = ctx.page.locator(selector).first
        if await outlooks_link.count() > 0:
            href = await outlooks_link.get_attribute("href")
            full_url = (
                "https://www.goldmansachs.com" + href if href.startswith("/") else href
            )
            logger.info(f"  [✓] Found Outlooks link: {full_url}")
            await ctx.add_requests([full_url])
    except SCRAPER_TRY_EXCEPTIONS as e:
        logger.error(f"  [!] Failed Insights Discovery: {e}")


async def _handle_homepage(ctx: PlaywrightCrawlingContext) -> None:
    logger.info("[STEP 1] Homepage → looking for Insights link")
    selector = "a[title='Explore Insights'], a:has-text('Explore Insights'), a[href='/insights']"
    try:
        insights_link = ctx.page.locator(selector).first
        if await insights_link.count() > 0:
            href = await insights_link.get_attribute("href")
            full_url = (
                "https://www.goldmansachs.com" + href if href.startswith("/") else href
            )
            logger.info(f"  [✓] Found Insights link: {full_url}")
            await ctx.page.goto(full_url, wait_until="load", timeout=30_000)
            await ctx.add_requests([ctx.page.url])
    except SCRAPER_TRY_EXCEPTIONS as e:
        logger.error(f"  [!] Failed Homepage Discovery: {e}")


async def main(
    lookback_days: int, max_articles: int, output_file: str | None = None
) -> None:
    scraper_cfg = load_scraper_config(SOURCE_NAME)
    output_file = output_file or scraper_cfg["output_file"]
    retry_settings = build_playwright_retry_defaults(scraper_cfg)

    # ── State lives inside main() ─────────────────────────────────────────────
    scraped_outlooks: list[Article] = []
    article_titles: dict[str, str] = {}
    stats = {"total_found": 0, "total_within_window": 0}

    # ── Isolate configuration to prevent asyncio.Lock event loop conflicts ─────
    config = Configuration(storage_dir=f"storage_{SOURCE_NAME}")

    # Camoufox (stealthed Firefox) is required — Goldman Sachs uses Akamai Bot Manager
    # which fingerprints TLS handshake and canvas/WebGL; plain Chromium is always detected.
    crawler = PlaywrightCrawler(
        configuration=config,
        browser_pool=build_camoufox_pool(),
        max_requests_per_crawl=max_articles,
        concurrency_settings=ConcurrencySettings(
            min_concurrency=1,
            max_concurrency=3,
            desired_concurrency=2,
        ),
        navigation_timeout=timedelta(seconds=90),
        request_handler_timeout=timedelta(seconds=120),
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

    # ── SINGLE HANDLER WITH MANUAL ROUTING ────────────────────────────────────
    @crawler.router.default_handler
    async def universal_handler(ctx: PlaywrightCrawlingContext) -> None:
        url = ctx.request.url
        logger.info(f"Processing: {url}")

        # 30s timeout: Camoufox/Firefox renders slightly slower than Chromium;
        # GS homepage is also heavy with lazy-loaded components.
        page_ready = await wait_for_any_selector(
            ctx.page,
            ["main", "article", "a[href*='/insights']", "nav"],
            timeout_ms=30000,
            source=SOURCE_NAME,
        )
        if not page_ready:
            page_html = await ctx.page.content()
            if detect_bot_block(page_html):
                raise RuntimeError(
                    "[ANTI_BOT_BLOCK] Goldman Sachs WAF challenge detected."
                )
            return
        await dismiss_overlays(ctx.page)

        is_homepage = url.strip("/") == START_URL.strip("/")
        is_outlooks_list = "/outlooks/2026-outlooks" in url
        is_article = (
            "/insights/articles/" in url
            or "/insights/goldman-sachs-research/" in url
            or "/insights/goldman-sachs-exchanges/" in url
            or "/investment-banking/insights/articles/" in url
        )
        is_insights_hub = "/insights" in url and not is_article and not is_outlooks_list

        if is_article:
            await _handle_article(
                ctx.page,
                url,
                {
                    "article_titles": article_titles,
                    "scraped_outlooks": scraped_outlooks,
                    "stats": stats,
                    "lookback_days": lookback_days,
                },
            )
            return

        if is_outlooks_list:
            await _handle_outlooks_list(ctx, url, article_titles, stats)
            return

        if is_insights_hub:
            await _handle_insights_hub(ctx)
            return

        if is_homepage:
            await _handle_homepage(ctx)
            return

    # ── Run ───────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Goldman Sachs Outlooks Scraper")
    logger.info(f"Entry : {START_URL}")
    logger.info(f"Out   : {output_file}")
    logger.info("=" * 60)

    await crawler.run([START_URL])

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Done. Articles scraped: {len(scraped_outlooks)}")
    logger.info("=" * 60)
    save_results(scraped_outlooks, stats, lookback_days, output_file, SOURCE_NAME)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goldman Sachs Outlooks Scraper")
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
    lookback_days_val = (
        args.lookback_days
        if args.lookback_days is not None
        else scraper_cfg_main["lookback_days"]
    )
    max_art_val = (
        args.max_articles
        if args.max_articles is not None
        else scraper_cfg_main["max_articles"]
    )
    OUTPUT_FILE_VAL = scraper_cfg_main["output_file"]

    asyncio.run(
        main(
            lookback_days=lookback_days_val,
            max_articles=max_art_val,
            output_file=OUTPUT_FILE_VAL,
        )
    )
