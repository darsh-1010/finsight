"""API routes for the Market Insights feature.

Provides endpoints to trigger manual watchlist scans, retrieve live immediate
alerts for premium tiers, and fetch weekly summary aggregates.
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.dependencies import get_ticker_service
from src.core.exceptions import AppError
from src.core.interfaces import ITickerService
from src.services.market_insights.daily_compiler import DailySummaryCompiler
from src.services.market_insights.llm_engine import LLMEngine
from src.services.market_insights.market_triggers import MarketTriggerService
from src.services.market_insights.models import ScanRequest, ScanResponse
from src.services.market_insights.notification_dispatcher import (
    NotificationDispatcher, build_dispatcher)
from src.services.market_insights.rag_client import MarketInsightsRAGClient
from src.services.market_insights.weekly_compiler import WeeklySummaryCompiler
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Default watchlist used when a scan request does not provide explicit tickers.
_DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "NFLX"]


@router.post("/scan", response_model=ScanResponse)
async def scan_watchlist(
    request: ScanRequest,
    dispatcher: NotificationDispatcher = Depends(build_dispatcher),
    ticker_service: ITickerService = Depends(get_ticker_service),
) -> ScanResponse:
    """Trigger a scan for a set of tickers or a default watchlist.

    Runs the event trigger detection, semantic RAG context retrieval,
    LLM 30-topic classification, and tier-based dispatching pipeline.
    """
    tickers = request.tickers if request.tickers else _DEFAULT_WATCHLIST
    logger.info(
        "[API_SCAN] User: %s | Tier: %d | Raw Watchlist: %s",
        request.user_id,
        request.user_tier,
        tickers,
    )

    # Resolve company names or user-friendly inputs to actual stock tickers
    resolved_tickers = []
    for t in tickers:
        stripped = t.strip()
        if not stripped:
            continue
        try:
            res_result = await ticker_service.resolve(stripped)
            resolved = res_result.get("ticker")
            if resolved:
                resolved_tickers.append(resolved)
            else:
                resolved_tickers.append(stripped.upper())
        except Exception as exc:
            logger.warning(
                "[API_SCAN_RESOLVE_FAIL] Failed to resolve: %s | Error: %s",
                stripped,
                exc,
            )
            resolved_tickers.append(stripped.upper())

    # Deduplicate resolved tickers
    resolved_tickers = list(dict.fromkeys(resolved_tickers))
    logger.info("[API_SCAN_RESOLVED] Resolved Watchlist: %s", resolved_tickers)

    trigger_service = MarketTriggerService()
    rag_client = MarketInsightsRAGClient()
    llm_engine = LLMEngine()

    try:
        # 1. Trigger detection
        events = await trigger_service.scan_watchlist(resolved_tickers)

        insights = []
        alerts_count = 0

        # 2. Process each detected event through RAG + LLM + Dispatch
        for event in events:
            try:
                # Retrieve RAG context chunks
                chunks = await rag_client.get_recent_context(event)

                # Classify event with LLM
                insight = await llm_engine.classify_event(event, chunks)
                insights.append(insight)

                # Dispatch notification based on user tier
                alert = await dispatcher.dispatch(
                    insight=insight,
                    user_id=request.user_id,
                    user_tier=request.user_tier,
                )
                if alert is not None:
                    alerts_count += 1
            except AppError as exc:
                logger.error(
                    "[API_SCAN_EVENT_FAIL] Ticker: %s | AppError: %s",
                    event.ticker,
                    exc,
                )
                continue
            except Exception as exc:
                logger.error(
                    "[API_SCAN_EVENT_UNEXPECTED] Ticker: %s | Unexpected Error: %s",
                    event.ticker,
                    exc,
                    exc_info=True,
                )
                continue

        return ScanResponse(
            scanned=len(resolved_tickers),
            events_detected=len(events),
            alerts_dispatched=alerts_count,
            insights=insights,
        )

    finally:
        rag_client.close()


@router.get("/alerts/immediate")
async def get_immediate_alerts(
    user_id: str = Header(..., alias="x-user-id"),
    user_tier: int = Header(default=1, alias="x-tier-id"),
    dispatcher: NotificationDispatcher = Depends(build_dispatcher),
):
    """Retrieve and drain all immediate alerts for premium tiers (Tiers 3 & 4)."""
    if user_tier not in (3, 4):
        raise HTTPException(
            status_code=403,
            detail="Immediate alert streaming is only available to premium tiers (Tiers 3 & 4).",
        )
    try:
        alerts = await dispatcher.get_pending_immediate(user_id)
        return {
            "success": True,
            "count": len(alerts),
            "alerts": alerts,
        }
    except Exception as exc:
        logger.error("[API_ALERTS_IMMEDIATE_FAIL] User: %s | Error: %s", user_id, exc)
        raise HTTPException(
            status_code=500, detail="Failed to fetch immediate alerts."
        ) from exc


@router.get("/alerts/weekly")
async def get_weekly_alerts(
    user_id: str = Header(..., alias="x-user-id"),
    user_tier: int = Header(default=1, alias="x-tier-id"),
    sync: bool = False,
    dispatcher: NotificationDispatcher = Depends(build_dispatcher),
):
    """Retrieve the compiled, fact-verified weekly summary report for Tiers 1, 2, 3, and 4."""
    if user_tier not in (1, 2, 3, 4):
        raise HTTPException(
            status_code=403,
            detail="Weekly summary aggregation is only available for Tiers 1, 2, 3, and 4.",
        )
    try:
        # 1. Fetch raw accumulated alert payloads from the Redis queue
        raw_alerts = await dispatcher.get_weekly_summary(user_id)

        # 2. Compile, fact-verify, and return the structured WeeklySummaryReport
        compiler = WeeklySummaryCompiler()
        if sync:
            logger.info(
                "[API_ALERTS_WEEKLY_SYNC] User: %s | Compiling report synchronously",
                user_id,
            )
            report = await compiler.generate_and_cache_summary(
                user_id, raw_alerts, user_tier
            )
            if not report:
                report = await compiler.get_or_generate_summary(
                    user_id, raw_alerts, user_tier
                )
        else:
            report = await compiler.get_or_generate_summary(
                user_id, raw_alerts, user_tier
            )

        return {
            "success": True,
            "report": report,
        }
    except Exception as exc:
        logger.error("[API_ALERTS_WEEKLY_FAIL] User: %s | Error: %s", user_id, exc)
        raise HTTPException(
            status_code=500, detail="Failed to compile weekly report."
        ) from exc


@router.get("/alerts/daily")
async def get_daily_alerts(
    user_id: str = Header(..., alias="x-user-id"),
    user_tier: int = Header(default=1, alias="x-tier-id"),
    sync: bool = False,
    dispatcher: NotificationDispatcher = Depends(build_dispatcher),
):
    """Retrieve the compiled, fact-verified daily summary report for premium tiers (Tiers 3 and 4)."""
    if user_tier not in (3, 4):
        raise HTTPException(
            status_code=403,
            detail="Daily summary aggregation is only available for premium tiers (Tiers 3 and 4).",
        )
    try:
        # 1. Fetch raw accumulated alert payloads from the Redis queue
        raw_alerts = await dispatcher.get_daily_summary(user_id)

        # 2. Compile, fact-verify, and return the structured DailySummaryReport
        compiler = DailySummaryCompiler()
        if sync:
            logger.info(
                "[API_ALERTS_DAILY_SYNC] User: %s | Compiling report synchronously",
                user_id,
            )
            report = await compiler.generate_and_cache_summary(
                user_id, raw_alerts, user_tier
            )
            if not report:
                report = await compiler.get_or_generate_summary(
                    user_id, raw_alerts, user_tier
                )
        else:
            report = await compiler.get_or_generate_summary(
                user_id, raw_alerts, user_tier
            )

        return {
            "success": True,
            "report": report,
        }
    except Exception as exc:
        logger.error("[API_ALERTS_DAILY_FAIL] User: %s | Error: %s", user_id, exc)
        raise HTTPException(
            status_code=500, detail="Failed to compile daily report."
        ) from exc
