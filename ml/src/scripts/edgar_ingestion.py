"""SEC EDGAR filing ingestion pipeline.

Fetches 10-K, 10-Q, 8-K filings for a set of tickers, applies
structure-aware chunking (respects filing section boundaries), and
stores chunks in Weaviate with full metadata.

Usage::

    python -m src.scripts.edgar_ingestion --tickers AAPL MSFT NVDA --types 10-K 10-Q

Or import and call programmatically::

    from src.scripts.edgar_ingestion import ingest_filings
    await ingest_filings(["AAPL"], filing_types=["10-K"], limit_per_type=3)
"""

import argparse
import asyncio
import re
from typing import Any

from src.data_sources.edgar_source import EdgarSource, SUPPORTED_FILING_TYPES
from src.services.rag.rag_service import RAGService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Section headers commonly found in SEC filings ──────────────────────────
# These regex patterns detect major section boundaries so we can chunk
# at semantically meaningful points instead of blindly splitting.
_10K_SECTIONS = re.compile(
    r"(?:^|\n)\s*(?:ITEM|Item)\s+"
    r"(1[AB]?|2|3|4|5|6|7[A]?|8|9[AB]?|1[0-5])"
    r"[\.\:\s\-—–]+",
    re.MULTILINE,
)

_GENERIC_SECTION = re.compile(
    r"(?:^|\n)\s*(?:"
    r"PART\s+(?:I{1,3}V?|V?I{0,3})"
    r"|SIGNATURES?"
    r"|EXHIBITS?\s+AND\s+FINANCIAL"
    r"|FINANCIAL\s+STATEMENTS"
    r"|MANAGEMENT['']?S?\s+DISCUSSION"
    r"|RISK\s+FACTORS?"
    r"|NOTES?\s+TO\s+(?:THE\s+)?(?:CONSOLIDATED\s+)?FINANCIAL"
    r"|REPORT\s+OF\s+INDEPENDENT"
    r"|SELECTED\s+FINANCIAL\s+DATA"
    r"|QUANTITATIVE\s+AND\s+QUALITATIVE"
    r")",
    re.MULTILINE | re.IGNORECASE,
)

# Target chunk size. SEC filings are long — we use larger chunks to preserve
# context within a section, but cap at 2000 chars for embedding quality.
_CHUNK_TARGET = 1800
_CHUNK_OVERLAP = 200
_MIN_CHUNK_LEN = 100


def _section_aware_split(text: str) -> list[dict[str, str]]:
    """Split filing text at section boundaries, then sub-chunk if needed.

    Returns list of dicts with 'content' and 'section' keys.
    """
    # Find all section break positions.
    breaks: list[tuple[int, str]] = []
    for m in _10K_SECTIONS.finditer(text):
        breaks.append((m.start(), f"Item {m.group(1)}"))
    for m in _GENERIC_SECTION.finditer(text):
        breaks.append((m.start(), m.group(0).strip()))

    # Sort by position, deduplicate nearby breaks.
    breaks.sort(key=lambda x: x[0])

    # If no sections found, fall back to positional chunking.
    if not breaks:
        return _positional_chunk(text, section="Full Document")

    chunks: list[dict[str, str]] = []
    for i, (start, section_name) in enumerate(breaks):
        end = breaks[i + 1][0] if i + 1 < len(breaks) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) < _MIN_CHUNK_LEN:
            continue
        chunks.extend(_positional_chunk(section_text, section=section_name))

    return chunks


def _positional_chunk(text: str, section: str = "") -> list[dict[str, str]]:
    """Split text into overlapping chunks of ~_CHUNK_TARGET chars."""
    chunks: list[dict[str, str]] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_TARGET
        # Try to break at a paragraph or sentence boundary.
        if end < len(text):
            # Look for paragraph break.
            para_break = text.rfind("\n\n", start + _CHUNK_TARGET // 2, end + 200)
            if para_break > start:
                end = para_break
            else:
                # Look for sentence break.
                sent_break = text.rfind(". ", start + _CHUNK_TARGET // 2, end + 100)
                if sent_break > start:
                    end = sent_break + 1

        chunk_text = text[start:end].strip()
        if len(chunk_text) >= _MIN_CHUNK_LEN:
            chunks.append({"content": chunk_text, "section": section})

        start = end - _CHUNK_OVERLAP if end < len(text) else len(text)

    return chunks


async def ingest_filings(
    tickers: list[str],
    *,
    filing_types: list[str] | None = None,
    limit_per_type: int = 3,
) -> dict[str, Any]:
    """Fetch and ingest SEC filings into the vector store.

    Args:
        tickers: Ticker symbols to ingest.
        filing_types: Which filing types (default: all supported).
        limit_per_type: Max filings per type per ticker.

    Returns:
        Summary dict with counts of filings processed and chunks stored.
    """
    types = filing_types or list(SUPPORTED_FILING_TYPES)
    edgar = EdgarSource()
    rag = RAGService()

    stats = {"filings_fetched": 0, "filings_ingested": 0, "chunks_stored": 0, "errors": 0}

    try:
        all_filings = await edgar.get_recent_filings_for_tickers(
            tickers, filing_types=types, limit_per_type=limit_per_type
        )
        stats["filings_fetched"] = len(all_filings)

        for filing in all_filings:
            try:
                url = filing["primary_document_url"]
                logger.info(
                    "[EDGAR_INGEST] Processing %s %s (%s)",
                    filing["ticker"],
                    filing["filing_type"],
                    filing["filing_date"],
                )

                text = await edgar.get_filing_text(url)
                if not text or len(text) < 500:
                    logger.warning("[EDGAR_INGEST] Skipping empty/short filing: %s", url)
                    continue

                # Structure-aware chunking.
                chunks = _section_aware_split(text)
                logger.info(
                    "[EDGAR_INGEST] Split into %d chunks for %s %s",
                    len(chunks), filing["ticker"], filing["filing_type"],
                )

                # Store each chunk with rich metadata.
                for i, chunk in enumerate(chunks):
                    metadata = {
                        "source_type": "sec_filing",
                        "ticker": filing["ticker"],
                        "company_name": filing["company_name"],
                        "filing_type": filing["filing_type"],
                        "filing_date": filing["filing_date"],
                        "section": chunk["section"],
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "accession_number": filing["accession_number"],
                        "cik": filing["cik"],
                    }

                    chunk_count = await rag.store_document(
                        url=f"{url}#chunk-{i}",
                        content=chunk["content"],
                        metadata=metadata,
                    )
                    stats["chunks_stored"] += chunk_count

                stats["filings_ingested"] += 1

            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                logger.error(
                    "[EDGAR_INGEST] Failed to process filing %s: %s",
                    filing.get("primary_document_url", "unknown"),
                    exc,
                )
                stats["errors"] += 1

    finally:
        await edgar.close()
        rag.close()

    logger.info("[EDGAR_INGEST] Complete: %s", stats)
    return stats


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR filings into Weaviate")
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="Ticker symbols to ingest (e.g. AAPL MSFT NVDA)",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["10-K", "10-Q"],
        choices=list(SUPPORTED_FILING_TYPES),
        help="Filing types to fetch (default: 10-K 10-Q)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Max filings per type per ticker (default: 3)",
    )
    args = parser.parse_args()

    result = asyncio.run(
        ingest_filings(args.tickers, filing_types=args.types, limit_per_type=args.limit)
    )
    print(f"\nIngestion complete: {result}")


if __name__ == "__main__":
    from src.scripts.path_bootstrap import bootstrap  # noqa: E402
    bootstrap()
    main()
