"""Main scrapper service that orchestrates PDF scraper."""

import asyncio
from typing import Optional

from src.utils.logger import get_logger

from .base import BaseScraper, ScraperResult
from .pdf_scraper import PDFScraper
from .resilience import SCRAPER_TRY_EXCEPTIONS

logger = get_logger(__name__)


class ScrapperService:
    """Main service for scraping PDF content.

    This service provides PDF scraping capabilities with automatic routing
    and batch processing support.

    Features:
    - Modular scraper architecture for easy extension
    - Automatic source type detection
    - Batch processing of multiple PDFs
    - Comprehensive error handling and logging
    - Async/await support for concurrent scraping
    """

    def __init__(self):
        """Initialize scrapper service."""
        # Initialize PDF scraper
        self.pdf_scraper = PDFScraper()

        # List of scrapers in priority order
        self.scrapers: list[BaseScraper] = [
            self.pdf_scraper,
        ]

        logger.info("[SCRAPER_SERVICE_INIT] Status: Success | Scrapers: PDF")

    async def scrape(self, url: str) -> ScraperResult:
        """Scrape content from a single URL using appropriate scraper.

        Args:
            url: URL to scrape

        Returns:
            ScraperResult with content or error information
        """
        logger.info("[SCRAPE_START] Url: %s", url)

        # Find appropriate scraper
        scraper = self._find_scraper(url)

        if not scraper:
            error_msg = "No suitable scraper found for this URL"
            logger.error(f"{error_msg}: {url}")
            return ScraperResult(
                url=url,
                content="",
                status="failed",
                error=error_msg,
            )

        # Execute scraper
        return await scraper.scrape(url)

    async def scrape_batch(self, urls: list[str], max_concurrent: int = 3) -> dict:
        """Scrape multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum number of concurrent scraping operations

        Returns:
            Dictionary containing results, success count, and failure count
        """
        logger.info(
            "[BATCH_SCRAPE_START] Count: %d | MaxConcurrent: %d",
            len(urls),
            max_concurrent,
        )

        results: list[ScraperResult] = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> ScraperResult:
            """Scrape with semaphore to limit concurrency."""
            async with semaphore:
                try:
                    return await self.scrape(url)
                except SCRAPER_TRY_EXCEPTIONS as e:
                    logger.error(f"Exception during scraping {url}: {str(e)}")
                    return ScraperResult(
                        url=url,
                        content="",
                        status="failed",
                        error=f"Exception: {str(e)}",
                    )

        # Execute all scraping tasks concurrently
        results = await asyncio.gather(
            *[scrape_with_semaphore(url) for url in urls],
            return_exceptions=False,
        )

        # Calculate statistics
        successful = sum(1 for r in results if r.status == "success")
        failed = len(results) - successful

        logger.info(
            "[BATCH_SCRAPE_COMPLETE] Success: %d | Failed: %d", successful, failed
        )

        return {
            "results": results,
            "total": len(results),
            "successful": successful,
            "failed": failed,
        }

    def _find_scraper(self, url: str) -> Optional[BaseScraper]:
        """Find appropriate scraper for the given URL.

        Args:
            url: URL to find scraper for

        Returns:
            Appropriate scraper instance or None if no scraper can handle it
        """
        for scraper in self.scrapers:
            if scraper.can_handle(url):
                logger.debug(
                    "[SCRAPER_MATCH] Type: %s | Url: %s",
                    scraper.__class__.__name__,
                    url,
                )
                return scraper

        return None

    def get_available_scrapers(self) -> list[str]:
        """Get list of available scraper types.

        Returns:
            List of scraper class names
        """
        return [scraper.__class__.__name__ for scraper in self.scrapers]

    async def scrape_and_store(self, url: str, vector_service) -> dict:
        """Scrape URL and store in vector database."""
        try:
            # Scrape content
            result = await self.scrape(url)

            if result.status != "success":
                return {
                    "url": url,
                    "status": "failed",
                    "error": result.error,
                    "chunks_stored": 0,
                }

            # Store in vector database
            chunks_count = await vector_service.store_document(
                url=url, content=result.content, metadata={"status": result.status}
            )

            return {
                "url": url,
                "status": "success",
                "chunks_stored": chunks_count,
                "content_length": len(result.content),
            }

        except SCRAPER_TRY_EXCEPTIONS as e:
            logger.error(f"Error in scrape_and_store: {str(e)}")
            return {"url": url, "status": "failed", "error": str(e), "chunks_stored": 0}
