"""PDF scraping utilities."""

import asyncio
import logging
import os
import re
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import httpx
import pdfplumber
from pypdf import PdfReader

from src.services.scrapper.base import ScraperResult
from src.utils.s3_utils import S3Downloader

try:
    pytesseract: ModuleType | None
    import pytesseract
except ImportError:  # pragma: no cover - optional OCR dependency
    pytesseract = None

try:
    convert_from_path: Callable[[str], list[object]] | None
    from pdf2image import convert_from_path
except ImportError:  # pragma: no cover - optional OCR dependency
    convert_from_path = None

logger = logging.getLogger(__name__)

# Limit internal multithreading in Tesseract OCR to prevent CPU core oversubscription
os.environ["OMP_THREAD_LIMIT"] = "1"

# Thread pool for CPU-bound PDF operations (text extraction, OCR).
# Default to 2 workers to keep extraction parallel without saturating typical 2–4 core deployments.
try:
    _pdf_workers = int(os.environ.get("PDF_SCRAPER_MAX_WORKERS", "2"))
    _pdf_workers = max(_pdf_workers, 1)
except (TypeError, ValueError):
    _pdf_workers = 2

_executor = ThreadPoolExecutor(max_workers=_pdf_workers)


@dataclass
class PDFMetadata:
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    page_count: int = 0


class PDFScraper:
    """
    Downloads and extracts text from PDF files using a tiered approach:
    1. PyPDF2 (Fastest, basic text)
    2. pdfplumber (Better for tables/layouts)
    3. OCR via Tesseract (For scanned images)
    """

    def __init__(self, timeout: int = 60, verify_ssl: bool = True) -> None:
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self._s3_downloader: S3Downloader | None = None

    @property
    def s3_downloader(self) -> S3Downloader:
        """Build the S3 downloader lazily so non-S3 flows do not require boto3."""
        if self._s3_downloader is None:
            self._s3_downloader = S3Downloader()
        return self._s3_downloader

    def can_handle(self, url: str) -> bool:
        """Check if this scraper can handle the given URL (PDF or S3)."""
        if not url:
            return False
        lower_url = url.lower().split("?")[0]
        return lower_url.endswith(".pdf") or S3Downloader.is_s3_url(url)

    async def scrape(self, url: str) -> ScraperResult:
        """Main entry point to scrape a PDF URL."""
        logger.info("Scraping PDF: %s", url)
        try:
            content, temp_path = await self._download_and_validate(url)
            if not content:
                # content will be None if validation fails but no exception raised
                return ScraperResult(
                    url=url, status="error", error="Failed to download or validate PDF"
                )

            loop = asyncio.get_event_loop()
            # Run CPU-bound extraction in thread pool to avoid blocking event loop
            text = await loop.run_in_executor(
                _executor, self._extract_text_from_pdf, temp_path
            )
            metadata = await loop.run_in_executor(
                _executor, self._extract_pdf_metadata, temp_path
            )

            # Cleanup
            Path(temp_path).unlink(missing_ok=True)
            if not text or len(text.strip()) < 10:
                logger.warning(
                    "Extracted text too short, might be a scanned PDF: %s",
                    url,
                )
                # We could trigger OCR here if needed, but keeping it simple for now
            return ScraperResult(
                url=url,
                status="success",
                content=text,
                metadata={
                    "title": metadata.title,
                    "author": metadata.author,
                    "page_count": metadata.page_count,
                    "creation_date": metadata.creation_date,
                },
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            httpx.HTTPStatusError,
            httpx.RequestError,
        ) as exc:
            logger.error("Error scraping PDF %s: %s", url, exc)
            return ScraperResult(url=url, status="error", error=str(exc))

    async def _download_and_validate(self, url: str) -> tuple[bytes | None, str]:
        """Downloads PDF (from HTTP or S3) and returns (content, temp_file_path)."""
        fd_handle, path = tempfile.mkstemp(suffix=".pdf")
        os_descriptor_closed = False

        try:
            if S3Downloader.is_s3_url(url):
                # Handle S3 Download
                success = self.s3_downloader.download_to_temp(url, path)
                if not success:
                    return None, path
                with open(path, "rb") as f_handle:
                    content = f_handle.read()
            else:
                # Handle HTTP Download
                async with httpx.AsyncClient(
                    verify=self.verify_ssl, follow_redirects=True, timeout=self.timeout
                ) as client:
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    content = response.content

                if not content.startswith(b"%PDF"):
                    logger.error("URL did not return a valid PDF: %s", url)
                    return None, path

                with open(path, "wb") as f_handle:
                    f_handle.write(content)

            # Close the file descriptor from mkstemp
            os.close(fd_handle)
            os_descriptor_closed = True

            return content, path

        except (httpx.HTTPError, OSError, ValueError) as exc:
            logger.error("Download failed for %s: %s", url, exc)
            if not os_descriptor_closed:
                os.close(fd_handle)
            return None, path

    def _extract_text_from_pdf(self, path: str) -> str:
        """Tiered extraction logic (PyPDF2 -> pdfplumber -> OCR). Runs in executor."""
        text = ""
        # 1. Try PyPDF2
        try:
            with open(path, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.debug("PyPDF2 extraction failed: %s", exc)

        # 2. Try pdfplumber if text is still empty/short
        if len(text.strip()) < 50:
            try:
                with pdfplumber.open(path) as pdf:
                    text = ""
                    for plumber_page in pdf.pages:
                        page_text = plumber_page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
                logger.debug("pdfplumber extraction failed: %s", exc)

        # 3. Fallback to OCR if still no text
        if len(text.strip()) < 50:
            logger.info("Triggering OCR for PDF...")
            try:
                if pytesseract is None or convert_from_path is None:
                    raise ImportError(
                        "OCR dependencies (pytesseract, pdf2image) are not installed."
                    )
                images = convert_from_path(path)
                text = ""
                for img in images:
                    text += pytesseract.image_to_string(img) + "\n"
            except ImportError:
                logger.warning(
                    "OCR dependencies (pytesseract, pdf2image) not installed — skipping OCR"
                )
            except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
                logger.error("OCR failed: %s", exc)

        return text

    def _extract_pdf_metadata(self, path: str) -> PDFMetadata:
        """Extracts metadata using pypdf. Runs in executor."""
        metadata = PDFMetadata()
        try:
            with open(path, "rb") as f:
                reader = PdfReader(f)
                info = reader.metadata
                metadata.page_count = len(reader.pages)
                if info:
                    metadata.title = info.title
                    metadata.author = info.author
                    metadata.subject = info.subject
                    metadata.creator = info.creator
                    metadata.producer = info.producer
                    metadata.creation_date = info.get("/CreationDate")
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.debug("Metadata extraction failed: %s", exc)
        return metadata

    @staticmethod
    def cleanup_text(text: str) -> str:
        """Cleans up extracted text by removing excessive whitespace."""
        if not text:
            return ""
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)
        return text.strip()
