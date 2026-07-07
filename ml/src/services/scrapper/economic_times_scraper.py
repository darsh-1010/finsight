"""Economic Times scraper — Crawlee BeautifulSoupCrawler implementation.

Uses Crawlee's ``BeautifulSoupCrawler`` to fetch the markets/stocks/news
listing page and individual article pages concurrently.  The ET website
is accessible via standard HTTP requests without anti-bot measures.

Supports date-based filtering via ``lookback_days`` — articles outside
the window are skipped based on their listing-page timestamp.
"""

import argparse
import asyncio
import logging
from datetime import timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

from crawlee._request import Request
from crawlee._types import ConcurrencySettings
from crawlee.configuration import Configuration
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

from src.services.schema.article_schema import (Article, ArticleMetadata,
                                                ScrapeOutput,
                                                load_scraper_config)

from .date_filter import is_within_lookback

logger = logging.getLogger(__name__)


class EconomicTimesScraper:
    """Scrapes news articles from the Economic Times markets section.

    Pipeline:
    1. Load the markets/stocks/news listing page
    2. Extract article links, titles, and dates from listing
    3. Follow pagination links
    4. Visit each article page to extract full content
    5. Filter by published_date against lookback_days
    """

    BASE_URL = "https://economictimes.indiatimes.com"
    SOURCE_NAME = "economic_times"

    LISTING_URLS = [
        "https://economictimes.indiatimes.com/markets/stocks/news",
        "https://economictimes.indiatimes.com/markets/commodities/news",
    ]

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
        self.max_concurrency = max_concurrency or cfg.get("max_concurrency", 4)
        self.request_timeout_sec = cfg.get("request_timeout_sec", 30)
        self.max_pages = cfg.get("max_pages", 3)

        self._articles: List[Article] = []
        self._total_found = 0
        self._total_within_window = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """Run the full pipeline synchronously."""
        return asyncio.run(self.scrape_async())

    async def scrape_async(self) -> List[Dict]:
        """Crawlee-based async pipeline."""
        self._articles = []
        self._total_found = 0
        self._total_within_window = 0

        # ── Isolate configuration to prevent asyncio.Lock event loop conflicts ─────
        config = Configuration(storage_dir=f"storage_{self.SOURCE_NAME}")

        crawler = BeautifulSoupCrawler(
            configuration=config,
            max_requests_per_crawl=self.max_articles
            + len(self.LISTING_URLS) * self.max_pages,
            concurrency_settings=ConcurrencySettings(
                max_concurrency=self.max_concurrency,
                desired_concurrency=self.max_concurrency,
            ),
            request_handler_timeout=timedelta(seconds=self.request_timeout_sec),
        )

        crawler = BeautifulSoupCrawler(
            configuration=config,
            max_requests_per_crawl=self.max_articles
            + len(self.LISTING_URLS) * self.max_pages,
            concurrency_settings=ConcurrencySettings(
                max_concurrency=self.max_concurrency,
                desired_concurrency=self.max_concurrency,
            ),
            request_handler_timeout=timedelta(seconds=self.request_timeout_sec),
        )

        crawler.router.default_handler(self._listing_handler)
        crawler.router.handler("listing_page")(self._listing_handler)
        crawler.router.handler("article")(self._article_handler)

        # Build initial requests with section metadata
        initial_requests = []
        for listing_url in self.LISTING_URLS:
            section = self._section_from_url(listing_url)
            initial_requests.append(
                Request.from_url(
                    listing_url,
                    user_data={"section": section, "page_num": 1},
                )
            )

        await crawler.run(initial_requests)

        # Save results
        output = ScrapeOutput(
            source=self.SOURCE_NAME,
            lookback_days=self.lookback_days,
            total_found=self._total_found,
            total_within_window=self._total_within_window or len(self._articles),
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
    # Request Handlers
    # ------------------------------------------------------------------

    async def _listing_handler(self, context: BeautifulSoupCrawlingContext) -> None:
        """Handle listing pages — extract article links."""
        url = context.request.url
        current_page = context.request.user_data.get("page_num", 1)
        section = context.request.user_data.get("section", "stocks")
        context.log.info(
            f"Processing listing: {url} (section: {section}, page: {current_page})"
        )
        soup = context.soup

        # ET uses <div class="eachStory"> for article tiles
        stories = soup.select(
            "div.eachStory, div.story-box, div[class*='clr flt topnews'], li.clearfix"
        )

        if not stories:
            # Fallback: find all links to /articleshow/
            links = soup.find_all("a", href=lambda h: h and "/articleshow/" in h)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 10:
                    continue

                full_url = urljoin(self.BASE_URL, href)
                self._total_found += 1

                await context.add_requests(
                    [
                        Request.from_url(
                            full_url,
                            label="article",
                            user_data={"listing_title": title, "section": section},
                        )
                    ]
                )
        else:
            await self._process_stories(context, stories, section)

        # Follow pagination
        next_page = current_page + 1
        if next_page <= self.max_pages:
            next_link = soup.find("a", class_="next") or soup.find(
                "a", string=lambda s: s and "Next" in s
            )
            if next_link:
                next_url = urljoin(self.BASE_URL, next_link["href"])
                context.log.info(f"  Following page {next_page}")
                await context.add_requests(
                    [
                        Request.from_url(
                            next_url,
                            label="listing_page",
                            user_data={"page_num": next_page, "section": section},
                        )
                    ]
                )

    async def _process_stories(
        self, context: BeautifulSoupCrawlingContext, stories, section: str
    ):
        """Helper to process stories and enqueue article requests."""
        for story in stories:
            anchor = story.find("a", href=lambda h: h and "/articleshow/" in h)
            if not anchor:
                continue

            title = anchor.get_text(strip=True)
            href = anchor.get("href", "")
            full_url = urljoin(self.BASE_URL, href)

            # Extract date from listing (if present)
            date_elem = story.find("time") or story.find(
                "span", class_=lambda c: c and "date" in c.lower()
            )
            listing_date = (
                (date_elem.get("datetime") or date_elem.get_text(strip=True))
                if date_elem
                else None
            )

            self._total_found += 1

            if not is_within_lookback(listing_date, self.lookback_days):
                context.log.info(f"  Skipping (outside window): {listing_date}")
                continue

            self._total_within_window += 1
            await context.add_requests(
                [
                    Request.from_url(
                        full_url,
                        label="article",
                        user_data={
                            "listing_title": title,
                            "listing_date": listing_date,
                            "section": section,
                        },
                    )
                ]
            )

    async def _article_handler(self, context: BeautifulSoupCrawlingContext) -> None:
        """Handle article pages — extract full news content."""
        url = context.request.url
        user_data = dict(context.request.user_data)
        listing_title = user_data.get("listing_title", "Unknown")
        context.log.info(f"Processing article: {listing_title[:60]}")

        published_date = self._extract_date(context.soup, user_data)
        if not is_within_lookback(published_date, self.lookback_days):
            context.log.info(f"  Discarding (outside window): {published_date}")
            return

        article = self._parse_article(
            context.soup,
            url,
            listing_title,
            published_date=published_date,
            user_data=user_data,
        )
        self._articles.append(article)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_date(soup, user_data: dict) -> str | None:
        """Extract published date from meta tags or visible elements."""
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date:
            return meta_date["content"]

        listing_date = user_data.get("listing_date")
        if listing_date:
            return listing_date

        date_span = soup.find("time") or soup.find(
            "span", class_=lambda c: c and "date" in c.lower()
        )
        if date_span:
            return date_span.get("datetime") or date_span.get_text(strip=True)
        return None

    def _parse_article(
        self, soup, url, listing_title, *, published_date, user_data
    ) -> Article:
        """Parse article content and metadata from soup."""
        heading = soup.find("h1")
        title = heading.get_text(strip=True) if heading else listing_title

        return Article(
            source=self.SOURCE_NAME,
            url=url,
            title=title,
            content=self._extract_body(soup),
            summary=self._extract_summary(soup),
            metadata=ArticleMetadata(
                published_date=published_date,
                author=self._extract_author(soup),
                category=self._extract_category(soup, user_data),
                tags=self._extract_tags(soup),
            ),
        )

    @staticmethod
    def _extract_summary(soup) -> str:
        """Extract summary from meta description."""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        return meta_desc["content"] if meta_desc else ""

    @staticmethod
    def _extract_author(soup) -> Optional[str]:
        """Extract author name from meta or span."""
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta:
            return author_meta["content"]

        author_elem = soup.find("span", class_=lambda c: c and "author" in c.lower())
        return author_elem.get_text(strip=True) if author_elem else None

    @staticmethod
    def _extract_body(soup) -> str:
        """Extract article body text.

        ET puts article text directly inside ``div.artText`` as text
        nodes / inline spans — NOT wrapped in ``<p>`` tags.  We first
        try ``<p>``-based extraction, then fall back to ``.get_text()``.
        """
        body_div = (
            soup.find("div", class_="artText")
            or soup.find("div", class_="Normal")
            or soup.find("article")
        )

        if not body_div:
            return ""

        # Remove unwanted elements before extracting text
        for tag in body_div.find_all(
            ["script", "style", "ins", "iframe", "figure", "aside", "nav", "button"]
        ):
            tag.decompose()
        for also in body_div.find_all(
            "div", class_=lambda c: c and "also" in c.lower()
        ):
            also.decompose()

        # Try <p>-based extraction first
        paragraphs = body_div.find_all("p")
        p_text = "\n".join(
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 20
        )
        if len(p_text) > 200:
            return p_text

        # Fallback: get_text() from the whole div (ET style)
        raw = body_div.get_text(separator="\n", strip=True)

        # Clean up boilerplate lines
        skip_phrases = (
            "also read",
            "also watch",
            "subscribe",
            "catch all the",
            "download the",
            "et prime",
            "et app",
            "(catch all",
            "listen to this article",
        )
        lines = []
        for line in raw.split("\n"):
            line = line.strip()
            if len(line) < 20:
                continue
            if any(p in line.lower() for p in skip_phrases):
                continue
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def _extract_category(soup, user_data: dict) -> str:
        """Extract category from breadcrumb or user_data."""
        section = user_data.get("section", "markets")
        breadcrumb = soup.find("nav", attrs={"aria-label": "breadcrumb"})
        if breadcrumb:
            crumbs = breadcrumb.find_all("a")
            if len(crumbs) >= 2:
                return crumbs[-1].get_text(strip=True)
        return section

    @staticmethod
    def _extract_tags(soup) -> list:
        """Extract tags from keywords meta tag."""
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            return [
                t.strip() for t in meta_keywords["content"].split(",") if t.strip()
            ][:10]
        return []

    @staticmethod
    def _section_from_url(url: str) -> str:
        """Derive section name from ET listing URL."""
        if "commodities" in url:
            return "commodities"
        if "forex" in url:
            return "forex"
        return "stocks"


# ----------------------------------------------------------------------
# CLI entry-point
# ----------------------------------------------------------------------


def main():
    """Instantiate the scraper and run it."""
    parser = argparse.ArgumentParser(description="Economic Times scraper")
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
    scraper = EconomicTimesScraper(
        lookback_days=args.lookback_days,
        max_articles=args.max_articles,
    )
    scraper.scrape()


if __name__ == "__main__":
    main()
