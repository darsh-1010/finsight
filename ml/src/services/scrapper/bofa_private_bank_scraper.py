"""BofA Private Bank Capital Market Outlook scraper.

Renders the JS listing page with Crawlee Playwright + Camoufox, enqueues article
pages, and optionally extracts full text from linked PDFs.
"""

import argparse
import asyncio
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from types import ModuleType
from typing import TypedDict, cast
from urllib.parse import urljoin

import requests
from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.browsers import BrowserPool
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from src.services.schema.article_schema import (Article, ArticleMetadata,
                                                ScrapeOutput,
                                                load_scraper_config)
from src.services.scrapper.bofa_private_bank_scripts import (
    ARTICLE_CONTENT_EVAL_JS, LISTING_TILES_EVAL_JS)
from src.services.scrapper.camoufox_plugin import CamoufoxPlugin
from src.services.scrapper.date_filter import is_within_lookback
from src.services.scrapper.resilience import (SCRAPER_TRY_EXCEPTIONS,
                                              build_playwright_retry_defaults,
                                              detect_bot_block,
                                              probe_available_selectors,
                                              wait_for_any_selector,
                                              wait_for_post_action_settle)

try:
    pypdf: ModuleType | None
    import pypdf
except ImportError:
    pypdf = None

try:
    pdfplumber: ModuleType | None
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://www.privatebank.bankofamerica.com"
MARKET_OUTLOOK_HINTS = ("market outlook", "market update", "capital market outlook")
BLOCKED_PDF_HINTS = ("cookie", "privacy", "terms", "legal", "security", "disclosure")
BLOCKED_PDF_TEXT_HINTS = (
    "cookie guide",
    "online privacy",
    "your privacy choices",
    "advertising practices",
)

_LISTING_SELECTORS: tuple[str, ...] = (
    "[data-component='ArticleCard']",
    "[data-component='InsightCard']",
    "[data-content-type]",
    "[class*='insight']",
    "[class*='article-card']",
    "[class*='card-']",
    "article",
    ".tile",
    ".article-card",
    "main a[href*='insights']",
    "h3 a",
)

_PDF_TIMEOUT_SEC = 60
_PDF_MIN_CHARS = 200
_PDF_SESSION = requests.Session()
_PDF_SESSION.headers.update(
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)


@dataclass(frozen=True, slots=True)
class BofaPrivateBankScraperTimingConfig:
    """Timing configuration parameters."""

    request_timeout_sec: int
    hydration_delay_ms: int
    article_settle_delay_ms: int
    selector_timeout_ms: int
    load_more_delay_ms: int
    max_load_more_clicks: int
    retire_after_pages: int


@dataclass(frozen=True, slots=True)
class BofaPrivateBankScraperConfig:
    """Scraper configuration parameters."""

    lookback_days: int
    max_articles: int
    output_file: str
    max_concurrency: int
    scrape_pdf: bool
    timing: BofaPrivateBankScraperTimingConfig


@dataclass(slots=True)
class BofaPrivateBankScrapeStats:
    """Stats tracking."""

    total_found: int = 0
    total_within_window: int = 0


class ArticlePageContent(TypedDict, total=False):
    """Article content schema."""

    title: str
    summary: str
    published_date: str | None
    pdf_url: str | None
    content: str
    word_count: int
    author: str | None


def _fetch_pdf_text(pdf_url: str) -> str:
    """Download a PDF and extract its full text."""
    if pypdf is None and pdfplumber is None:
        logger.warning(
            "PDF extraction dependencies are missing; skipping PDF processing."
        )
        return ""

    try:
        logger.info("Downloading PDF: %s", pdf_url)
        resp = _PDF_SESSION.get(pdf_url, timeout=_PDF_TIMEOUT_SEC)
        resp.raise_for_status()
        pdf_bytes = resp.content
    except (
        ValueError,
        TypeError,
        AttributeError,
        RuntimeError,
        requests.RequestException,
    ) as exc:
        logger.warning("PDF download failed (%s): %s", pdf_url, exc)
        return ""

    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            text = "".join(page.extract_text() or "" for page in reader.pages).strip()
            if len(text) >= _PDF_MIN_CHARS:
                logger.info(
                    "PDF extracted via pypdf: %d chars (%s)", len(text), pdf_url
                )
                return text
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.debug("pypdf extraction failed: %s", exc)

    if pdfplumber is not None:
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = "".join(
                    (page.extract_text() or "") for page in pdf.pages
                ).strip()
            if len(text) >= _PDF_MIN_CHARS:
                logger.info(
                    "PDF extracted via pdfplumber: %d chars (%s)", len(text), pdf_url
                )
                return text
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.debug("pdfplumber extraction failed: %s", exc)

    logger.warning(
        "PDF text extraction yielded < %d chars: %s", _PDF_MIN_CHARS, pdf_url
    )
    return ""


def _normalize_value(value: str | None) -> str:
    """Return a normalized lowercase string for matching."""
    return (value or "").strip().lower()


def _contains_hint(value: str | None, hints: tuple[str, ...]) -> bool:
    """Return True when any hint appears in the normalized value."""
    normalized = _normalize_value(value)
    return bool(normalized) and any(hint in normalized for hint in hints)


async def _probe_and_log_dom(page: object, source: str) -> None:
    """Probe current DOM for any matching selectors and log results."""
    probe_candidates = [
        "article",
        "section",
        "[class*='card']",
        "[class*='tile']",
        "[class*='insight']",
        "[data-component]",
        "main div",
        "ul li a",
    ]
    found = await probe_available_selectors(page, probe_candidates)
    if found:
        logger.error(
            "[SELECTOR_DRIFT_ALERT] Source: %s | No primary selectors matched. "
            "DOM probes found: %s — update _LISTING_SELECTORS with these.",
            source,
            found,
        )
    else:
        logger.error(
            "[SELECTOR_DRIFT_ALERT] Source: %s | No selectors found at all. "
            "Page may be behind a bot-block or fully dynamic JS.",
            source,
        )


class BofAPrivateBankScraper:
    """Scrapes Capital Market Outlook articles from BofA Private Bank."""

    TARGET_URL = "https://www.privatebank.bankofamerica.com/insights.html"
    SOURCE_NAME = "bofa_private_bank"

    def __init__(
        self,
        lookback_days: int | None = None,
        max_articles: int | None = None,
        output_file: str | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        cfg = load_scraper_config(self.SOURCE_NAME)

        timing = BofaPrivateBankScraperTimingConfig(
            request_timeout_sec=cfg.get("request_timeout_sec", 90),
            hydration_delay_ms=cfg.get("hydration_delay_ms", 8000),
            article_settle_delay_ms=cfg.get("article_settle_delay_ms", 3000),
            selector_timeout_ms=cfg.get("selector_timeout_ms", 20000),
            load_more_delay_ms=cfg.get("load_more_delay_ms", 3000),
            max_load_more_clicks=cfg.get("max_load_more_clicks", 10),
            retire_after_pages=cfg.get("retire_after_pages", 5),
        )
        self.config = BofaPrivateBankScraperConfig(
            lookback_days=(
                lookback_days if lookback_days is not None else cfg["lookback_days"]
            ),
            max_articles=(
                max_articles if max_articles is not None else cfg["max_articles"]
            ),
            output_file=output_file if output_file is not None else cfg["output_file"],
            max_concurrency=(
                max_concurrency
                if max_concurrency is not None
                else cfg.get("max_concurrency", 1)
            ),
            scrape_pdf=cfg.get("scrape_pdf", True),
            timing=timing,
        )
        self.stats = BofaPrivateBankScrapeStats()
        self.retry_settings = build_playwright_retry_defaults(cfg)
        self._articles: list[Article] = []

    @staticmethod
    def _is_market_outlook_page(url: str, title: str, listing_title: str) -> bool:
        """Return True when the page is a verified market-outlook style article."""
        combined = " ".join(
            [
                _normalize_value(url),
                _normalize_value(title),
                _normalize_value(listing_title),
            ]
        )
        return any(hint in combined for hint in MARKET_OUTLOOK_HINTS)

    @staticmethod
    def _is_blocked_pdf_url(pdf_url: str | None) -> bool:
        """Return True when the PDF URL points to privacy or legal boilerplate."""
        return _contains_hint(pdf_url, BLOCKED_PDF_HINTS)

    @staticmethod
    def _is_valid_pdf_text(pdf_text: str, article_title: str) -> bool:
        """Return True when extracted PDF text appears relevant to the article."""
        if _contains_hint(pdf_text[:2000], BLOCKED_PDF_TEXT_HINTS):
            return False
        return _contains_hint(article_title, MARKET_OUTLOOK_HINTS)

    def scrape(self) -> list[dict[str, object]] | None:
        """Run the full pipeline synchronously."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> list[dict[str, object]] | None:
        """Crawlee-based async pipeline with concurrent article + PDF scraping."""
        self._articles = []
        self.stats.total_found = 0
        self.stats.total_within_window = 0

        storage_dir = os.path.join(os.getcwd(), f"storage_{self.SOURCE_NAME}")
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir, ignore_errors=True)

        pdf_executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrency,
            thread_name_prefix="bofa-pdf",
        )

        config = Configuration(storage_dir=storage_dir)
        crawler = PlaywrightCrawler(
            configuration=config,
            concurrency_settings=ConcurrencySettings(
                max_concurrency=self.config.max_concurrency,
                desired_concurrency=self.config.max_concurrency,
            ),
            request_handler_timeout=timedelta(
                seconds=self.config.timing.request_timeout_sec
            ),
            browser_pool=BrowserPool(
                plugins=[CamoufoxPlugin()],
                retire_browser_after_page_count=self.config.timing.retire_after_pages,
            ),
            navigation_timeout=timedelta(
                seconds=self.config.timing.request_timeout_sec
            ),
            **self.retry_settings,
        )

        @crawler.router.default_handler
        async def listing_handler(context: PlaywrightCrawlingContext) -> None:
            await self._handle_listing_page(context)

        @crawler.router.handler("article")
        async def article_handler(context: PlaywrightCrawlingContext) -> None:
            await self._handle_article_page(context, pdf_executor)

        try:
            await crawler.run([self.TARGET_URL])
        finally:
            pdf_executor.shutdown(wait=False)

        output = ScrapeOutput(
            source=self.SOURCE_NAME,
            lookback_days=self.config.lookback_days,
            total_found=self.stats.total_found,
            total_within_window=self.stats.total_within_window,
            total_scraped=len(self._articles),
            articles=self._articles,
        )
        output.save(self.config.output_file)
        logger.info(
            "Saved %d/%d articles (lookback=%dd) \u2192 %s",
            len(self._articles),
            self.stats.total_found,
            self.config.lookback_days,
            self.config.output_file,
        )
        return [a.to_dict() for a in self._articles] if self._articles else None

    @staticmethod
    def _is_listing_page_blocked(page_content: str) -> bool:
        block_signals = (
            "Access Denied",
            "Please enable JS",
            "unable to authorize your request",
            "403 Forbidden",
        )
        return any(signal in page_content for signal in block_signals)

    async def _handle_listing_page(self, context: PlaywrightCrawlingContext) -> None:
        context.log.info("Loading listing page: %s", context.request.url)
        context.log.info("Waiting for listing tiles to hydrate\u2026")

        page_ready = await wait_for_any_selector(
            context.page,
            list(_LISTING_SELECTORS),
            timeout_ms=self.config.timing.hydration_delay_ms + 20000,
            source=self.SOURCE_NAME,
        )

        if not page_ready:
            page_html = await context.page.content()
            if detect_bot_block(page_html):
                context.log.error(
                    "[BOT_BLOCK] BofA listing page returned a WAF challenge — aborting."
                )
            else:
                await _probe_and_log_dom(context.page, self.SOURCE_NAME)
            return

        await self._load_more_insights(context)

        raw_rows = cast(
            list[dict[str, object]],
            await context.page.evaluate(LISTING_TILES_EVAL_JS),
        )
        self.stats.total_found = len(raw_rows)
        context.log.info(
            "Found %d article rows on listing page.", self.stats.total_found
        )
        if self.stats.total_found == 0:
            context.log.warning(
                "No rows extracted \u2014 the page structure may have changed."
            )
            return

        await self._enqueue_listing_rows(context, raw_rows)

    async def _load_more_insights(self, context: PlaywrightCrawlingContext) -> None:
        load_more_selector = (
            'button:has-text("Explore more insights"), .tile__explore-more'
        )
        for attempt_index in range(self.config.timing.max_load_more_clicks):
            try:
                button = await context.page.query_selector(load_more_selector)
                if not button or not await button.is_visible():
                    context.log.info(
                        "No more 'Explore more' button found after %d clicks.",
                        attempt_index,
                    )
                    return

                context.log.info(
                    "Clicking 'Explore more insights' (Attempt %d/%d)...",
                    attempt_index + 1,
                    self.config.timing.max_load_more_clicks,
                )
                await button.click()
                await wait_for_post_action_settle(
                    context.page,
                    ["article", ".tile", ".article-card", "h3 a"],
                    timeout_ms=self.config.timing.load_more_delay_ms + 5000,
                )
            except SCRAPER_TRY_EXCEPTIONS as exc:
                context.log.warning("Load more failed or timed out: %s", exc)
                return

    async def _enqueue_listing_rows(
        self,
        context: PlaywrightCrawlingContext,
        raw_rows: list[dict[str, object]],
    ) -> None:
        articles_enqueued = 0
        for row in raw_rows:
            if articles_enqueued >= self.config.max_articles:
                return

            article_url = str(row.get("url", "") or "")
            listing_date = cast(str | None, row.get("date"))
            blurb = str(row.get("blurb", "") or "")
            title = str(row.get("title", "") or "")

            if not article_url:
                continue
            if article_url.startswith("/"):
                article_url = urljoin(BASE_URL, article_url)

            if not is_within_lookback(listing_date, self.config.lookback_days):
                context.log.info(
                    "  Skipping (outside %dd window): %s",
                    self.config.lookback_days,
                    listing_date,
                )
                continue

            self.stats.total_within_window += 1
            articles_enqueued += 1

            await context.add_requests(
                [
                    Request.from_url(
                        article_url,
                        label="article",
                        user_data={
                            "listing_date": listing_date,
                            "listing_blurb": blurb,
                            "listing_title": title,
                        },
                    )
                ]
            )
            context.log.info("  Enqueued: %s \u2192 %s", listing_date, article_url)

    async def _handle_article_page(
        self,
        context: PlaywrightCrawlingContext,
        pdf_executor: ThreadPoolExecutor,
    ) -> None:
        url = context.request.url
        listing_date, listing_blurb, listing_title = self._read_listing_user_data(
            context
        )

        context.page.set_default_navigation_timeout(
            self.config.timing.request_timeout_sec * 1000
        )
        context.page.set_default_timeout(self.config.timing.selector_timeout_ms)
        await wait_for_any_selector(
            context.page,
            ["h1", "article", "main"],
            timeout_ms=self.config.timing.article_settle_delay_ms + 5000,
            require_visible=True,
        )

        await self._wait_for_article_heading(context, url)

        content = cast(
            ArticlePageContent, await context.page.evaluate(ARTICLE_CONTENT_EVAL_JS)
        )
        published_date = content.get("published_date") or listing_date
        pdf_url = content.get("pdf_url")

        final_content, pdf_extracted = await self._resolve_article_content(
            context=context,
            content=content,
            listing_title=listing_title,
            pdf_url=pdf_url,
            pdf_executor=pdf_executor,
        )

        tags = self._build_article_tags(pdf_url, pdf_extracted)

        article = Article(
            source=self.SOURCE_NAME,
            url=url,
            title=content.get("title") or listing_title or "Insights",
            content=final_content,
            summary=listing_blurb or content.get("summary") or "",
            metadata=ArticleMetadata(
                published_date=published_date,
                author=content.get("author"),
                category="Market Updates",
                tags=tags,
            ),
        )
        if article.word_count < 50:
            context.log.warning("Low word count (%d) for: %s", article.word_count, url)

        self._articles.append(article)
        context.log.info(
            "  Saved: '%s' (%d words, date=%s, pdf=%s)",
            article.title[:60],
            article.word_count,
            published_date,
            "yes" if pdf_extracted else "no",
        )

    @staticmethod
    def _read_listing_user_data(
        context: PlaywrightCrawlingContext,
    ) -> tuple[str | None, str, str]:
        listing_date = cast(str | None, context.request.user_data.get("listing_date"))
        listing_blurb = str(context.request.user_data.get("listing_blurb", "") or "")
        listing_title = str(context.request.user_data.get("listing_title", "") or "")
        return listing_date, listing_blurb, listing_title

    async def _wait_for_article_heading(
        self, context: PlaywrightCrawlingContext, url: str
    ) -> None:
        try:
            await context.page.wait_for_selector(
                "h1", timeout=self.config.timing.selector_timeout_ms
            )
        except SCRAPER_TRY_EXCEPTIONS as exc:
            context.log.warning(
                "h1 not found within %.1fs on: %s (%s) \u2014 using listing data.",
                self.config.timing.selector_timeout_ms / 1000,
                url,
                exc,
            )

    async def _resolve_article_content(
        self,
        *,
        context: PlaywrightCrawlingContext,
        content: ArticlePageContent,
        listing_title: str,
        pdf_url: str | None,
        pdf_executor: ThreadPoolExecutor,
    ) -> tuple[str, bool]:
        url = context.request.url
        html_body = str(content.get("content", "") or "")
        if not self.config.scrape_pdf:
            return html_body, False

        page_title = str(content.get("title", "") or "")
        should_attempt_pdf = self._is_market_outlook_page(
            url=url,
            title=page_title,
            listing_title=listing_title,
        )
        if not pdf_url or not should_attempt_pdf:
            if pdf_url and not should_attempt_pdf:
                context.log.info(
                    "  Skipping PDF extraction for non-market-outlook page: %s", url
                )
            return html_body, False
        if self._is_blocked_pdf_url(pdf_url):
            context.log.warning("  Rejected blocked PDF URL: %s", pdf_url)
            return html_body, False

        context.log.info("  Fetching PDF: %s", pdf_url)
        loop = asyncio.get_running_loop()
        pdf_text = await loop.run_in_executor(pdf_executor, _fetch_pdf_text, pdf_url)
        if pdf_text and self._is_valid_pdf_text(pdf_text, page_title or listing_title):
            context.log.info("  PDF extracted: %d chars", len(pdf_text))
            return pdf_text, True

        context.log.warning(
            "  PDF validation failed \u2014 falling back to HTML body for: %s", url
        )
        return html_body, False

    @staticmethod
    def _build_article_tags(pdf_url: str | None, pdf_extracted: bool) -> list[str]:
        tags = ["Capital Market Outlook"]
        if pdf_url:
            tags.append(f"pdf:{pdf_url}")
        if pdf_extracted:
            tags.append("pdf_extracted")
        return tags


# CLI entry-point
def main() -> None:
    """Instantiate the scraper and run it via the CLI."""
    parser = argparse.ArgumentParser(
        description="BofA Private Bank — Capital Market Outlook scraper"
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only scrape articles from the last N days (default: from config)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Maximum number of articles to scrape (default: from config)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    scraper = BofAPrivateBankScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
