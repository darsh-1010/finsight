"""API routes for the Research Report feature.

Provides a single endpoint that resolves a ticker/company name and returns a
structured, cited research report combining live yFinance fundamentals with
the company's latest SEC 10-K filing.
"""

import re

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_research_service, get_ticker_service
from src.core.exceptions import YFinanceError
from src.core.interfaces import ITickerService
from src.core.schemas import ResearchReportRequest, ResearchReportResponse
from src.services.research.report_compiler import ResearchReportCompiler
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Minimum tier required to access research reports - Starter (tier 1) is
# explicitly "no asset-specific guidance" in the product's own tier copy.
_MIN_RESEARCH_TIER = 2

# A bare ticker symbol looks like this; anything else (e.g. "Apple", "hdfc bank")
# goes through TickerService's company-name resolution instead.
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")


@router.post("/research/report", response_model=ResearchReportResponse)
async def get_research_report(
    request: ResearchReportRequest,
    compiler: ResearchReportCompiler = Depends(get_research_service),
    ticker_service: ITickerService = Depends(get_ticker_service),
) -> ResearchReportResponse:
    """Generate (or fetch a cached) research report for a ticker or company name."""
    if request.tier < _MIN_RESEARCH_TIER:
        raise HTTPException(
            status_code=403,
            detail=f"Research reports require tier {_MIN_RESEARCH_TIER} or higher.",
        )

    raw_input = request.ticker.strip()
    ticker = raw_input.upper()
    if not _TICKER_PATTERN.match(ticker):
        resolution = await ticker_service.resolve(raw_input)
        resolved = resolution.get("ticker")
        if not resolved:
            raise HTTPException(
                status_code=404,
                detail=f"Could not resolve '{raw_input}' to a stock ticker.",
            )
        ticker = resolved

    logger.info("[RESEARCH_REPORT_REQUEST] Input: %s | Ticker: %s", raw_input, ticker)

    try:
        return await compiler.get_or_generate_report(ticker)
    except YFinanceError as exc:
        logger.warning("[RESEARCH_REPORT_NOT_FOUND] Ticker: %s | %s", ticker, exc)
        raise HTTPException(
            status_code=404, detail=f"No market data found for ticker '{ticker}'."
        ) from exc
