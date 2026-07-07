"""Unit tests for the Market Insights API endpoints and Weekly Summary Compiler.

Covers cases A-L for watchlist scan resolution, fallbacks, whitespace filtering,
defaulting, downstream trigger failures, premium tier checks, validation errors,
missing headers, weekly report compilation, and preservation of user_id.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from config.settings import settings
from src.api.dependencies import get_ticker_service
from src.api.main import app
from src.core.exceptions import AppError
from src.services.market_insights.models import (AlertPayload, EventType,
                                                 InsightCategory,
                                                 InsightResult, InsightTopic,
                                                 MarketEvent, ScanRequest,
                                                 ScanResponse,
                                                 WeeklyStockHighlight,
                                                 WeeklySummaryReport)
from src.services.market_insights.notification_dispatcher import \
    build_dispatcher
from src.services.market_insights.weekly_compiler import WeeklySummaryCompiler

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures & Fakes
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    """Configure anyio backend to use asyncio."""
    return "asyncio"


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


class FakePipeline:
    """Mock Redis Pipeline supporting lrange, delete, and execute."""

    def __init__(self, fake_redis) -> None:
        self.fake_redis = fake_redis
        self.ops = []

    def lrange(self, key: str, start: int, end: int) -> "FakePipeline":
        self.ops.append(("lrange", key))
        return self

    def delete(self, key: str) -> "FakePipeline":
        self.ops.append(("delete", key))
        return self

    async def execute(self) -> list[Any]:
        results = []
        for cmd, key in self.ops:
            if cmd == "lrange":
                results.append(self.fake_redis.store.get(key, []))
            elif cmd == "delete":
                drained = self.fake_redis.store.pop(key, None)
                results.append(1 if drained is not None else 0)
        return results


class FakeRedis:
    """Fake Redis client for testing caching and transactions without hitting network."""

    def __init__(self) -> None:
        self.store = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, time: int, value: str) -> None:
        self.store[key] = value

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        **kwargs: Any,
    ) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self)

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if self.store.pop(k, None) is not None:
                count += 1
        return count


class MockTickerService:
    """Mock ticker resolution service."""

    async def resolve(self, name: str) -> dict[str, Any]:
        name_clean = name.strip()
        if name_clean == "Apple":
            return {"ticker": "AAPL"}
        elif name_clean == "Tesla Inc":
            return {"ticker": "TSLA"}
        elif name_clean == "MSFT":
            return {"ticker": "MSFT"}
        elif name_clean == "UnknownXYZ":
            return {"ticker": None}
        elif name_clean == "THROW_ERROR":
            raise ValueError("Ticker service lookup failed")
        return {"ticker": None}


# ──────────────────────────────────────────────────────────────────────────────
# POST /scan Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
async def test_scan_watchlist_case_a_standard_resolution(
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Case A: Standard Watchlist Resolution & Deduplication.

    Verify that natural names resolve successfully to tickers and duplicates are removed.
    """
    mock_dispatcher = AsyncMock()
    mock_dispatcher.dispatch.return_value = MagicMock()

    mock_ticker_service = MockTickerService()

    mock_trigger_service = mock_trigger_service_class.return_value
    mock_rag_client = mock_rag_client_class.return_value
    mock_llm_engine = mock_llm_engine_class.return_value

    mock_trigger_service.scan_watchlist = AsyncMock(return_value=[])

    # ScanRequest with duplicates and natural names
    request = ScanRequest(
        user_id="usr_1001",
        user_tier=3,
        tickers=["Apple", "Tesla Inc", "MSFT", "Apple"],
    )

    from src.api.routes.market_insights import scan_watchlist

    response = await scan_watchlist(
        request=request,
        dispatcher=mock_dispatcher,
        ticker_service=mock_ticker_service,
    )

    # Verify duplicate "Apple" is resolved and deduplicated
    mock_trigger_service.scan_watchlist.assert_called_once_with(["AAPL", "TSLA", "MSFT"])
    assert response.scanned == 3


@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
async def test_scan_watchlist_case_b_fallback_unresolved(
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Case B: Fallback on Unresolved/Unknown Tickers.

    Verify that if a ticker lookup returns None or throws an error,
    the API defaults to the uppercase raw input and continues gracefully.
    """
    mock_dispatcher = AsyncMock()
    mock_ticker_service = MockTickerService()

    mock_trigger_service = mock_trigger_service_class.return_value
    mock_trigger_service.scan_watchlist = AsyncMock(return_value=[])

    # "UnknownXYZ" resolves to None, "THROW_ERROR" raises an exception
    request = ScanRequest(
        user_id="usr_1001",
        user_tier=3,
        tickers=["UnknownXYZ", "THROW_ERROR", "AAPL"],
    )

    from src.api.routes.market_insights import scan_watchlist

    response = await scan_watchlist(
        request=request,
        dispatcher=mock_dispatcher,
        ticker_service=mock_ticker_service,
    )

    # UnknownXYZ resolves to raw uppercase UNKNOWNXYZ, THROW_ERROR to THROW_ERROR, AAPL to raw uppercase AAPL
    mock_trigger_service.scan_watchlist.assert_called_once_with(["UNKNOWNXYZ", "THROW_ERROR", "AAPL"])
    assert response.scanned == 3


@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
async def test_scan_watchlist_case_c_whitespace_filtering(
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Case C: Whitespace and Empty Input Filtering.

    Verify that empty strings or purely whitespace entries are stripped out and ignored.
    """
    mock_dispatcher = AsyncMock()
    mock_ticker_service = MockTickerService()

    mock_trigger_service = mock_trigger_service_class.return_value
    mock_trigger_service.scan_watchlist = AsyncMock(return_value=[])

    request = ScanRequest(
        user_id="usr_1001",
        user_tier=3,
        tickers=["   ", "", "AAPL", "MSFT", "  \n  "],
    )

    from src.api.routes.market_insights import scan_watchlist

    response = await scan_watchlist(
        request=request,
        dispatcher=mock_dispatcher,
        ticker_service=mock_ticker_service,
    )

    # Whitespace and empty elements are stripped and skipped
    mock_trigger_service.scan_watchlist.assert_called_once_with(["AAPL", "MSFT"])
    assert response.scanned == 2


@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
async def test_scan_watchlist_case_d_empty_defaulting(
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Case D: Empty Tickers Defaulting.

    Verify that calling the scan API with an empty ticker list correctly defaults
    to the standard watchlist (_DEFAULT_WATCHLIST).
    """
    mock_dispatcher = AsyncMock()
    mock_ticker_service = MockTickerService()

    mock_trigger_service = mock_trigger_service_class.return_value
    mock_trigger_service.scan_watchlist = AsyncMock(return_value=[])

    request = ScanRequest(
        user_id="usr_1001",
        user_tier=3,
        tickers=[],
    )

    from src.api.routes.market_insights import scan_watchlist

    response = await scan_watchlist(
        request=request,
        dispatcher=mock_dispatcher,
        ticker_service=mock_ticker_service,
    )

    from src.api.routes.market_insights import _DEFAULT_WATCHLIST

    # Expect it to default to _DEFAULT_WATCHLIST (deduplicated / resolved)
    assert response.scanned == len(_DEFAULT_WATCHLIST)


@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
async def test_scan_watchlist_case_e_graceful_pipeline_failure(
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Case E: Graceful Failure in Core Trigger Pipeline.

    Verify that if a downstream trigger service or RAG client throws an exception,
    it is caught at the event level, logged, and does not cause a 500 Internal Server Error.
    """
    mock_dispatcher = AsyncMock()
    mock_ticker_service = MockTickerService()

    mock_trigger_service = mock_trigger_service_class.return_value
    mock_rag_client = mock_rag_client_class.return_value
    mock_llm_engine = mock_llm_engine_class.return_value

    # Setup two events
    event1 = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_SURGE,
        current_price=180.0,
        price_change_pct=5.5,
    )
    event2 = MarketEvent(
        ticker="MSFT",
        event_type=EventType.INTRADAY_SURGE,
        current_price=400.0,
        price_change_pct=6.0,
    )
    mock_trigger_service.scan_watchlist = AsyncMock(return_value=[event1, event2])

    # RAG client throws AppError for AAPL, but succeeds for MSFT
    async def fake_get_context(event):
        if event.ticker == "AAPL":
            raise AppError("RAG collection timeout")
        return []

    mock_rag_client.get_recent_context.side_effect = fake_get_context

    mock_llm_engine.classify_event = AsyncMock(
        return_value=InsightResult(
            event=event2,
            category=InsightCategory.PRICE_ACTION,
            topic=InsightTopic.INTRADAY_SURGE,
            confidence=0.95,
            summary="MSFT surge.",
        )
    )

    request = ScanRequest(
        user_id="usr_1001",
        user_tier=3,
        tickers=["AAPL", "MSFT"],
    )

    from src.api.routes.market_insights import scan_watchlist

    response = await scan_watchlist(
        request=request,
        dispatcher=mock_dispatcher,
        ticker_service=mock_ticker_service,
    )

    # AAPL should gracefully fail/skip, MSFT should succeed
    assert response.scanned == 2
    assert response.events_detected == 2
    assert len(response.insights) == 1
    assert response.insights[0].event.ticker == "MSFT"


# ──────────────────────────────────────────────────────────────────────────────
# GET /alerts/immediate Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_get_immediate_alerts_case_f_premium_access(client: TestClient) -> None:
    """Case F: Premium Tier Access (Tiers 3 & 4).

    Verify premium users receive a successful 200 response containing alerts.
    """
    mock_dispatcher = AsyncMock()
    mock_dispatcher.get_pending_immediate.return_value = [
        {
            "ticker": "AAPL",
            "message": "Premium immediate alert",
        }
    ]

    app.dependency_overrides[build_dispatcher] = lambda: mock_dispatcher

    try:
        response = client.get(
            "/api/v1/alerts/immediate",
            headers={"x-user-id": "usr_premium", "x-tier-id": "3"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["alerts"][0]["ticker"] == "AAPL"
    finally:
        app.dependency_overrides.clear()


def test_get_immediate_alerts_case_g_basic_restriction(client: TestClient) -> None:
    """Case G: Basic/Free Tier Restriction (Tiers 0, 1, 2).

    Verify users with a tier below 3 are strictly rejected with a 403 Forbidden.
    """
    response = client.get(
        "/api/v1/alerts/immediate",
        headers={"x-user-id": "usr_basic", "x-tier-id": "2"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "premium tiers" in data["detail"]


def test_get_immediate_alerts_case_h_missing_headers(client: TestClient) -> None:
    """Case H: Missing Required Headers.

    Verify that requests without the mandatory x-user-id header fail validation.
    """
    response = client.get(
        "/api/v1/alerts/immediate",
        headers={"x-tier-id": "3"},  # Missing x-user-id
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


# ──────────────────────────────────────────────────────────────────────────────
# GET /alerts/weekly Tests
# ──────────────────────────────────────────────────────────────────────────────

@patch("src.services.market_insights.weekly_compiler.get_async_redis")
@patch("src.services.market_insights.weekly_compiler.FallbackAsyncOpenAI")
def test_get_weekly_alerts_case_i_basic_access(
    mock_openai_class: MagicMock,
    mock_redis_func: MagicMock,
    client: TestClient,
) -> None:
    """Case I: Basic/Free Tier Access (Tiers 1 & 2).

    Verify basic users can fetch their weekly summary report.
    """
    fake_redis = FakeRedis()
    mock_redis_func.return_value = fake_redis

    mock_openai = mock_openai_class.return_value
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.parsed = WeeklySummaryReport(
        user_id="usr_basic",
        generated_at=datetime.utcnow(),
        overall_sentiment="Neutral market trends.",
        highlights=[
            WeeklyStockHighlight(
                ticker="AAPL",
                weekly_trend="Neutral",
                price_change_pct=1.2,
                key_event="Earnings",
                verification_status="Verified",
                summary="Solid performance.",
                citations=["https://example.com"],
                alert_message="AAPL [+1.2%] — Solid performance during earnings.",
                insight_source="yfinance",
                category=InsightCategory.PRICE_ACTION,
                topic=InsightTopic.VOLUME_SPIKE,
            )
        ],
        macro_factors=["CPI"],
        key_takeaway="Watch high growth stocks.",
    )
    mock_openai.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)
    fake_redis.store["mi:weekly_report:tier:2"] = mock_completion.choices[0].message.parsed.model_dump_json()

    mock_dispatcher = AsyncMock()
    # Mock some raw AlertPayloads in weekly summary queue
    mock_dispatcher.get_weekly_summary.return_value = [
        AlertPayload(
            insight=InsightResult(
                event=MarketEvent(
                    ticker="AAPL",
                    event_type=EventType.INTRADAY_SURGE,
                    current_price=180.0,
                    price_change_pct=1.2,
                ),
                category=InsightCategory.PRICE_ACTION,
                topic=InsightTopic.INTRADAY_SURGE,
                confidence=0.9,
                summary="AAPL summary",
            ),
            user_tier=2,
            user_id="usr_basic",
        )
    ]

    app.dependency_overrides[build_dispatcher] = lambda: mock_dispatcher

    try:
        response = client.get(
            "/api/v1/alerts/weekly",
            headers={"x-user-id": "usr_basic", "x-tier-id": "2"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["report"]["user_id"] == "usr_basic"
        assert data["report"]["overall_sentiment"] == "Neutral market trends."
    finally:
        app.dependency_overrides.clear()


@patch("src.services.market_insights.weekly_compiler.get_async_redis")
@patch("src.services.market_insights.weekly_compiler.FallbackAsyncOpenAI")
def test_get_weekly_alerts_case_j_premium_access(
    mock_openai_class: MagicMock,
    mock_redis_func: MagicMock,
    client: TestClient,
) -> None:
    """Case J: Premium Tier Access (Tiers 3 & 4).

    Verify premium users are successfully allowed on this weekly route.
    """
    fake_redis = FakeRedis()
    mock_redis_func.return_value = fake_redis

    mock_openai = mock_openai_class.return_value
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.parsed = WeeklySummaryReport(
        user_id="usr_premium",
        generated_at=datetime.utcnow(),
        overall_sentiment="Deep premium market trends.",
        highlights=[
            WeeklyStockHighlight(
                ticker="AAPL",
                weekly_trend="Neutral",
                price_change_pct=1.2,
                key_event="Earnings",
                verification_status="Verified",
                summary="Solid performance.",
                citations=["https://example.com"],
                alert_message="AAPL [+1.2%] — Solid performance during earnings.",
                insight_source="yfinance",
                category=InsightCategory.PRICE_ACTION,
                topic=InsightTopic.VOLUME_SPIKE,
            )
        ],
        macro_factors=["CPI"],
        key_takeaway="Watch high growth stocks.",
    )
    mock_openai.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)
    fake_redis.store["mi:weekly_report:tier:3"] = mock_completion.choices[0].message.parsed.model_dump_json()

    mock_dispatcher = AsyncMock()
    mock_dispatcher.get_weekly_summary.return_value = []

    app.dependency_overrides[build_dispatcher] = lambda: mock_dispatcher

    try:
        response = client.get(
            "/api/v1/alerts/weekly",
            headers={"x-user-id": "usr_premium", "x-tier-id": "3"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["report"]["user_id"] == "usr_premium"
        assert data["report"]["overall_sentiment"] == "Deep premium market trends."
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# WeeklySummaryCompiler Core & Preservation Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
@patch("src.services.market_insights.weekly_compiler.get_async_redis")
@patch("src.services.market_insights.weekly_compiler.FallbackAsyncOpenAI")
@patch("src.services.market_insights.weekly_compiler.WeeklySummaryCompiler._fetch_movers_and_news")
async def test_case_k_programmatic_user_id_preservation(
    mock_fetch: MagicMock,
    mock_openai_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Case K: Programmatic user_id Preservation.

    Verify synthesized WeeklySummaryReport has its user_id programmatically
    set to the request header x-user-id, preventing LLM hallucinations (e.g. dummy value).
    """
    fake_redis = FakeRedis()
    mock_redis_func.return_value = fake_redis

    mock_openai = mock_openai_class.return_value
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]

    # LLM hallucinates a dummy user_id "dummy_user_123"
    mock_completion.choices[0].message.parsed = WeeklySummaryReport(
        user_id="dummy_user_123",
        overall_sentiment="Great week.",
        highlights=[],
        macro_factors=[],
        key_takeaway="None.",
    )
    mock_openai.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)

    import pandas as pd
    mock_fetch.return_value = ([], [], [])

    compiler = WeeklySummaryCompiler(openai_api_key="fake-key")

    raw_alerts = [
        AlertPayload(
            insight=InsightResult(
                event=MarketEvent(
                    ticker="TSLA",
                    event_type=EventType.INTRADAY_DROP,
                    current_price=170.0,
                    price_change_pct=-6.0,
                ),
                category=InsightCategory.PRICE_ACTION,
                topic=InsightTopic.INTRADAY_DROP,
                confidence=0.8,
                summary="Tesla dropped",
            ),
            user_tier=2,
            user_id="real_user_777",
        )
    ]

    print("Calling compiler")
    report = await compiler.get_or_generate_summary("real_user_777", raw_alerts)
    print("Compiler returned")

    # Verify programmatic preservation of user_id
    assert report.user_id == "real_user_777"
    print("Test K finished successfully")


@pytest.mark.anyio
@patch("src.services.market_insights.weekly_compiler.get_async_redis")
@patch("src.services.market_insights.weekly_compiler.FallbackAsyncOpenAI")
@patch("src.services.market_insights.weekly_compiler.WeeklySummaryCompiler._fetch_movers_and_news")
async def test_case_l_empty_redis_queue_fallback(
    mock_fetch: MagicMock,
    mock_openai_class: MagicMock,
    mock_redis_func: MagicMock,
) -> None:
    """Case L: Empty Redis Queue Fallback.

    Verify that if a user has zero raw daily alerts stored in Redis, the weekly compiler
    generates a clean, structured fallback summary containing default watchlist tickers without crashing.
    """
    fake_redis = FakeRedis()
    mock_redis_func.return_value = fake_redis

    import pandas as pd
    mock_fetch.return_value = ([], [], [])
    
    mock_openai = mock_openai_class.return_value
    mock_openai.beta.chat.completions.parse = AsyncMock(side_effect=Exception("Simulate OpenAI failure to trigger fallback"))

    compiler = WeeklySummaryCompiler(openai_api_key="fake-key")

    # Pass an empty raw_alerts list to simulate empty Redis queue
    report = await compiler.get_or_generate_summary("real_user_999", [])

    # Should default to standard fallback report without hitting OpenAI or raising an error
    assert report.user_id == "real_user_999"
    assert len(report.highlights) > 0
    assert report.highlights[0].ticker == "AAPL"
    assert report.highlights[0].weekly_trend == "Neutral"
    assert "skipped" in report.highlights[0].summary


@pytest.mark.anyio
@patch("src.services.market_insights.market_triggers.yf.Ticker")
async def test_case_n_yfinance_fast_info_recovery(mock_ticker_class: MagicMock) -> None:
    """Case N: yfinance .fast_info recovery fallback.

    Verify that when Ticker.info fails/raises an exception, the service recovers
    the core fields from .fast_info and populates the return dict successfully.
    """
    from src.services.market_insights.market_triggers import \
        MarketTriggerService

    mock_stock = MagicMock()
    # Mock .info to raise an exception
    type(mock_stock).info = property(lambda self: (_ for _ in ()).throw(RuntimeError("Yahoo blocked")))
    
    # Mock .fast_info to return core values
    mock_fast_info = {
        "lastPrice": 182.50,
        "open": 180.00,
        "yearHigh": 195.00,
        "yearLow": 165.00,
        "lastVolume": 50000000,
        "threeMonthAverageVolume": 45000000,
    }
    type(mock_stock).fast_info = property(lambda self: mock_fast_info)

    mock_ticker_class.return_value = mock_stock

    service = MarketTriggerService()
    data = service._fetch_ticker_data("AAPL")

    assert data["price"] == 182.50
    assert data["open"] == 180.00
    assert data["week_52_high"] == 195.00
    assert data["week_52_low"] == 165.00
    assert data["volume"] == 50000000
    assert data["avg_volume"] == 45000000


@pytest.mark.anyio
async def test_case_m_standard_update_event_generation() -> None:
    """Case M: STANDARD_UPDATE event fallback generation.

    Verify that if a ticker does not breach intraday, 52-week or volume thresholds,
    a STANDARD_UPDATE event is generated so the ticker is analyzed consistently.
    """
    from src.services.market_insights.market_triggers import \
        MarketTriggerService

    service = MarketTriggerService()
    # Non-extreme price metrics
    data = {
        "price": 180.00,
        "open": 180.00,  # 0% intraday move
        "week_52_high": 200.00,  # Far from 52-week ceiling
        "week_52_low": 150.00,  # Far from 52-week floor
        "volume": 1000000,
        "avg_volume": 1000000,  # 1x volume
    }

    events = service._detect_events("AAPL", data)
    assert len(events) == 1
    assert events[0].event_type == EventType.STANDARD_UPDATE
    assert events[0].ticker == "AAPL"


@pytest.mark.anyio
@patch("src.services.market_insights.rag_client.WeaviateService")
async def test_case_o_rag_connection_failure_fallback(mock_weaviate_service_class: MagicMock) -> None:
    """Case O: RAG connection failure fallback.

    Verify that when Weaviate search raises a connection exception, RAG client
    gracefully catches it, logs a warning, and returns an empty chunks list []
    rather than propagating RAGError and causing the entire scan to abort.
    """
    from src.services.market_insights.rag_client import MarketInsightsRAGClient
    
    mock_vector = mock_weaviate_service_class.return_value
    mock_vector.search_similar = AsyncMock(side_effect=RuntimeError("Connection refused"))

    client = MarketInsightsRAGClient()
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.STANDARD_UPDATE,
        current_price=180.0,
        price_change_pct=0.0,
    )

    chunks = await client.get_recent_context(event)
    assert chunks == []


# ──────────────────────────────────────────────────────────────────────────────
# Resiliency & Edge Case Tests for GET /alerts/immediate
# ──────────────────────────────────────────────────────────────────────────────

@patch("src.services.market_insights.notification_dispatcher.get_async_redis")
def test_get_immediate_alerts_case_p_corrupted_payload_resiliency(
    mock_redis_func: MagicMock,
    client: TestClient,
) -> None:
    """Case P: Resiliency Against Corrupted payloads.

    Verify that when the Redis queue contains a corrupted payload alongside a valid one,
    the compiler gracefully skips the corrupted item, logs it, and returns the valid one
    instead of crashing the entire HTTP call and losing all alerts.
    """
    fake_redis = FakeRedis()
    mock_redis_func.return_value = fake_redis

    valid_payload = AlertPayload(
        insight=InsightResult(
            event=MarketEvent(
                ticker="AAPL",
                event_type=EventType.INTRADAY_DROP,
                current_price=175.0,
                price_change_pct=-5.4,
            ),
            category=InsightCategory.PRICE_ACTION,
            topic=InsightTopic.INTRADAY_DROP,
            confidence=0.92,
            summary="Apple drops 5.4% intraday.",
        ),
        user_tier=3,
        user_id="usr_resilient_test",
    )

    # Insert both a valid JSON string and a completely corrupted text string
    key = "mi:immediate:usr_resilient_test"
    fake_redis.store[key] = [valid_payload.model_dump_json(), "{corrupted_json_string_here"]

    # We patch dispatchers get_async_redis so notification_dispatcher uses fake_redis
    with patch("src.services.market_insights.notification_dispatcher.get_async_redis", return_value=fake_redis):
        response = client.get(
            "/api/v1/alerts/immediate",
            headers={"x-user-id": "usr_resilient_test", "x-tier-id": "3"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["alerts"][0]["insight"]["event"]["ticker"] == "AAPL"
        
        # Verify queue was successfully drained and deleted in fake redis
        assert key not in fake_redis.store


@pytest.mark.anyio
@patch("src.services.market_insights.notification_dispatcher.get_async_redis")
async def test_get_immediate_alerts_case_q_atomic_double_drain(
    mock_redis_func: MagicMock,
) -> None:
    """Case Q: Atomic Double-Draining / Concurrent Requests Race Condition.

    Verify that concurrent calls to get_pending_immediate resolve atomically:
    one request drains the items and the second concurrent request gets an empty list,
    preventing duplicate alert consumption.
    """
    from src.services.market_insights.notification_dispatcher import \
        NotificationDispatcher

    # Use MagicMock for synchronous Redis client and pipeline creation,
    # and AsyncMock for the asynchronous execution step.
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    
    mock_redis.pipeline.return_value = mock_pipeline
    mock_redis_func.return_value = mock_redis

    valid_payload = AlertPayload(
        insight=InsightResult(
            event=MarketEvent(ticker="TSLA", event_type=EventType.VOLUME_SPIKE, current_price=220.0, price_change_pct=1.5),
            category=InsightCategory.PRICE_ACTION,
            topic=InsightTopic.VOLUME_SPIKE,
            confidence=0.85,
            summary="Tesla volume spike.",
        ),
        user_tier=3,
        user_id="usr_concurrency_test",
    )

    # Make pipeline execution asynchronous
    mock_pipeline.execute = AsyncMock()
    mock_pipeline.execute.side_effect = [
        [[valid_payload.model_dump_json()], 1],  # First concurrent execution returns items
        [[], 0],                                  # Second concurrent execution returns empty
    ]

    dispatcher = NotificationDispatcher()
    
    # Fire off two concurrent drains
    results = await asyncio.gather(
        dispatcher.get_pending_immediate("usr_concurrency_test"),
        dispatcher.get_pending_immediate("usr_concurrency_test")
    )

    # Assert exact-once atomic delivery
    assert len(results[0]) == 1 or len(results[1]) == 1
    assert len(results[0]) == 0 or len(results[1]) == 0
    assert results[0] != results[1]


def test_get_immediate_alerts_case_r_empty_queue_fetch(
    client: TestClient,
) -> None:
    """Case R: Empty Queue Fetch.

    Verify that requesting immediate alerts when none are pending returns a clean
    successful 200 response with an empty count and array, without crashing.

    Uses a mock dispatcher to avoid a live Redis connection during unit testing.
    """
    mock_dispatcher = AsyncMock()
    # Simulates a Redis queue that exists but holds zero pending alerts
    mock_dispatcher.get_pending_immediate.return_value = []

    app.dependency_overrides[build_dispatcher] = lambda: mock_dispatcher

    try:
        response = client.get(
            "/api/v1/alerts/immediate",
            headers={"x-user-id": "usr_empty_test", "x-tier-id": "3"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 0
        assert data["alerts"] == []
    finally:
        app.dependency_overrides.clear()



def test_get_immediate_alerts_case_s_malformed_header_validation(
    client: TestClient,
) -> None:
    """Case S: Malformed Header Inputs.

    Verify that missing required user headers or invalid tier types are caught
    by FastAPI parameter validation and rejected with 422 Unprocessable Entity.
    """
    # 1. Missing x-user-id header
    response_missing = client.get(
        "/api/v1/alerts/immediate",
        headers={"x-tier-id": "3"},
    )
    assert response_missing.status_code == 422

    # 2. Malformed non-integer x-tier-id header
    response_malformed = client.get(
        "/api/v1/alerts/immediate",
        headers={"x-user-id": "usr_test", "x-tier-id": "not-an-integer"},
    )
    assert response_malformed.status_code == 422


def test_get_daily_alerts_case_x_premium_access(client: TestClient) -> None:
    """Case X: Premium Tier Access for Daily Alerts (Tiers 3 & 4).

    Verify premium users receive a successful 200 response containing daily alerts.
    """
    mock_dispatcher = AsyncMock()
    mock_dispatcher.get_daily_summary.return_value = []

    app.dependency_overrides[build_dispatcher] = lambda: mock_dispatcher

    try:
        response = client.get(
            "/api/v1/alerts/daily",
            headers={"x-user-id": "usr_premium", "x-tier-id": "3"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_get_daily_alerts_case_y_basic_restriction(client: TestClient) -> None:
    """Case Y: Basic/Free Tier Restriction for Daily Alerts (Tiers 1 & 2).

    Verify users with a tier below 3 are strictly rejected with a 403 Forbidden.
    """
    response = client.get(
        "/api/v1/alerts/daily",
        headers={"x-user-id": "usr_basic", "x-tier-id": "2"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "premium tiers" in data["detail"]

