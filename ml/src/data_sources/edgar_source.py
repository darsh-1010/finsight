"""SEC EDGAR data source — fetches 10-K, 10-Q, 8-K filings.

Uses the free EDGAR FULL-TEXT SEARCH API (efts.sec.gov) and the
company-filings API (data.sec.gov). No API key required; only a
User-Agent header identifying the caller (SEC fair-access policy).

SEC rate limit: 10 requests/second — enforced via asyncio.Semaphore.
"""

import asyncio
import re
from typing import Any

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

# SEC requires a descriptive User-Agent (company/app + contact email).
_SEC_USER_AGENT = "FinSight/1.0 (contact@chatfinsight.ai)"

# Respect SEC's 10 req/s limit globally.
_SEC_SEMAPHORE = asyncio.Semaphore(8)

# Filing types we care about.
SUPPORTED_FILING_TYPES = frozenset({"10-K", "10-Q", "8-K"})

# Max filings to fetch per request.
_DEFAULT_LIMIT = 10

# HTTP timeout for SEC requests.
_HTTP_TIMEOUT = 30.0


class EdgarSource:
    """Fetch SEC filings for a given ticker/CIK.

    Usage::

        source = EdgarSource()
        filings = await source.get_filings("AAPL", filing_type="10-K", limit=5)
        text = await source.get_filing_text(filing_url)
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=_HTTP_TIMEOUT,
                headers={"User-Agent": _SEC_USER_AGENT, "Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Public API ───────────────────────────────────────────────────────────

    async def resolve_cik(self, ticker: str) -> str | None:
        """Resolve a ticker symbol to a zero-padded 10-digit CIK.

        Uses the SEC company tickers JSON endpoint.
        """
        client = await self._ensure_client()
        url = "https://www.sec.gov/files/company_tickers.json"

        async with _SEC_SEMAPHORE:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("[EDGAR] CIK resolution failed for %s: %s", ticker, exc)
                return None

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry["cik_str"]).zfill(10)
                logger.info("[EDGAR] Resolved %s → CIK %s", ticker, cik)
                return cik

        logger.info("[EDGAR] No CIK found for ticker %s", ticker)
        return None

    async def get_filings(
        self,
        ticker: str,
        *,
        filing_type: str = "10-K",
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Return recent filings metadata for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").
            filing_type: One of 10-K, 10-Q, 8-K.
            limit: Max filings to return.

        Returns:
            List of dicts with keys: accession_number, filing_date,
            primary_document_url, filing_type, company_name.
        """
        if filing_type not in SUPPORTED_FILING_TYPES:
            logger.warning("[EDGAR] Unsupported filing type: %s", filing_type)
            return []

        cik = await self.resolve_cik(ticker)
        if not cik:
            return []

        client = await self._ensure_client()
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"

        async with _SEC_SEMAPHORE:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("[EDGAR] Failed to fetch filings for %s: %s", ticker, exc)
                return []

        company_name = data.get("name", ticker)
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])

        filings: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != filing_type:
                continue
            if len(filings) >= limit:
                break

            accession = accessions[i].replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik.lstrip('0')}/{accession}/{primary_docs[i]}"
            )

            filings.append({
                "ticker": ticker.upper(),
                "company_name": company_name,
                "filing_type": form,
                "filing_date": dates[i],
                "accession_number": accessions[i],
                "primary_document_url": doc_url,
                "cik": cik,
            })

        logger.info(
            "[EDGAR] Found %d %s filings for %s", len(filings), filing_type, ticker
        )
        return filings

    async def get_filing_text(self, url: str, *, max_chars: int = 500_000) -> str:
        """Download and extract text from a filing document.

        Handles both HTML filings (strips tags) and plain-text filings.
        Caps output at `max_chars` to prevent memory issues on massive filings.
        """
        client = await self._ensure_client()
        logger.debug("[EDGAR] Downloading filing: %s", url)

        async with _SEC_SEMAPHORE:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                raw = resp.text
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("[EDGAR] Failed to download filing: %s | %s", url, exc)
                return ""

        # Strip HTML tags if the document is HTML.
        if "<html" in raw[:500].lower() or "<body" in raw[:500].lower():
            text = _strip_html(raw)
        else:
            text = raw

        # Normalize whitespace.
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        if len(text) > max_chars:
            text = text[:max_chars]
            logger.info("[EDGAR] Truncated filing text to %d chars", max_chars)

        return text.strip()

    async def get_recent_filings_for_tickers(
        self,
        tickers: list[str],
        *,
        filing_types: list[str] | None = None,
        limit_per_type: int = 3,
    ) -> list[dict[str, Any]]:
        """Fetch recent filings for multiple tickers concurrently.

        Args:
            tickers: List of ticker symbols.
            filing_types: Filing types to fetch (defaults to all supported).
            limit_per_type: Max filings per type per ticker.

        Returns:
            Flat list of filing metadata dicts.
        """
        types = filing_types or list(SUPPORTED_FILING_TYPES)
        tasks = []
        for ticker in tickers:
            for ft in types:
                tasks.append(
                    self.get_filings(ticker, filing_type=ft, limit=limit_per_type)
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_filings: list[dict[str, Any]] = []
        for res in results:
            if isinstance(res, list):
                all_filings.extend(res)
            elif isinstance(res, Exception):
                logger.warning("[EDGAR] Batch filing fetch error: %s", res)

        logger.info("[EDGAR] Fetched %d total filings for %d tickers",
                    len(all_filings), len(tickers))
        return all_filings


def _strip_html(html: str) -> str:
    """Naive but fast HTML tag stripper — good enough for SEC filings."""
    # Remove script and style blocks.
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags.
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities.
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&nbsp;", " "), ("&quot;", '"'), ("&#39;", "'")]:
        text = text.replace(entity, char)
    # Collapse the whitespace left behind by each stripped tag becoming a space.
    return " ".join(text.split())
