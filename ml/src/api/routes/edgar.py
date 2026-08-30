"""SEC EDGAR ingestion API routes.

Exposes endpoints for triggering EDGAR filing ingestion and querying
available filings for a ticker. Designed for admin/internal use.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.data_sources.edgar_source import SUPPORTED_FILING_TYPES, EdgarSource
from src.scripts.edgar_ingestion import ingest_filings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/edgar", tags=["edgar"])


class IngestionRequest(BaseModel):
    """Request body for filing ingestion."""

    tickers: list[str] = Field(
        ..., min_length=1, max_length=20,
        description="Ticker symbols to ingest",
    )
    filing_types: list[str] = Field(
        default=["10-K", "10-Q"],
        description="Filing types to fetch",
    )
    limit_per_type: int = Field(
        default=3, ge=1, le=10,
        description="Max filings per type per ticker",
    )


class IngestionResponse(BaseModel):
    """Response from ingestion endpoint."""

    status: str
    filings_fetched: int
    filings_ingested: int
    chunks_stored: int
    errors: int


@router.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(request: IngestionRequest) -> IngestionResponse:
    """Trigger SEC EDGAR filing ingestion for specified tickers.

    This is a potentially long-running operation. For production use,
    consider wrapping in a background task.
    """
    # Validate filing types.
    for ft in request.filing_types:
        if ft not in SUPPORTED_FILING_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported filing type: {ft}. Supported: {sorted(SUPPORTED_FILING_TYPES)}",
            )

    logger.info(
        "[EDGAR_API] Ingestion triggered | tickers=%s | types=%s | limit=%d",
        request.tickers,
        request.filing_types,
        request.limit_per_type,
    )

    try:
        result = await ingest_filings(
            tickers=request.tickers,
            filing_types=request.filing_types,
            limit_per_type=request.limit_per_type,
        )
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("[EDGAR_API] Ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "[EDGAR_API] Ingestion complete | fetched=%d | ingested=%d | chunks=%d | errors=%d",
        result["filings_fetched"], result["filings_ingested"],
        result["chunks_stored"], result["errors"],
    )

    return IngestionResponse(
        status="completed",
        filings_fetched=result["filings_fetched"],
        filings_ingested=result["filings_ingested"],
        chunks_stored=result["chunks_stored"],
        errors=result["errors"],
    )


@router.get("/filings/{ticker}")
async def list_filings(
    ticker: str,
    filing_type: str = Query(default="10-K", description="Filing type"),
    limit: int = Query(default=5, ge=1, le=20, description="Max results"),
) -> dict[str, Any]:
    """List available SEC filings for a ticker (metadata only, no ingestion)."""
    if filing_type not in SUPPORTED_FILING_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported filing type: {filing_type}",
        )

    logger.info("[EDGAR_API] Listing filings | ticker=%s | type=%s | limit=%d", ticker, filing_type, limit)
    source = EdgarSource()
    try:
        filings = await source.get_filings(ticker, filing_type=filing_type, limit=limit)
        logger.info("[EDGAR_API] Found %d filings for %s", len(filings), ticker)
        return {"ticker": ticker.upper(), "filing_type": filing_type, "filings": filings}
    except (RuntimeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await source.close()
