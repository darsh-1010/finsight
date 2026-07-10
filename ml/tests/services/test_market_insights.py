"""Unit tests for the Market Insights notification pipeline.

Tests event detection, RAG retrieval, LLM classification, and Redis-backed
notification dispatching with premium/basic tier logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.market_insights.llm_engine import LLMEngine
from src.services.market_insights.market_triggers import MarketTriggerService
from src.services.market_insights.models import (EventType, InsightCategory,
                                                 InsightResult, InsightTopic,
                                                 MarketEvent)
from src.services.market_insights.notification_dispatcher import \
    NotificationDispatcher
from src.services.market_insights.rag_client import MarketInsightsRAGClient


@pytest.fixture
def anyio_backend():
    """Configure anyio backend to use asyncio."""
    return "asyncio"


# ──────────────────────────────────────────────────────────────────────────────
# Trigger Layer Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@patch("yfinance.Ticker")
async def test_market_trigger_detection(mock_ticker_class: MagicMock) -> None:
    """Test yfinance-based scanning and event triggers."""
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "currentPrice": 90.0,
        "open": 100.0,  # 10% drop
        "fiftyTwoWeekHigh": 180.0,
        "fiftyTwoWeekLow": 89.9,  # within 0.5% tolerance of 52W low
        "volume": 5000000,
        "averageVolume": 1000000,  # 5x volume spike
    }
    mock_ticker_class.return_value = mock_ticker

    service = MarketTriggerService()
    events = await service.scan_watchlist(["AAPL"])

    # Should detect drop, 52w low, and volume spike
    detected_types = {e.event_type for e in events}
    assert EventType.INTRADAY_DROP in detected_types
    assert EventType.WEEK_52_LOW in detected_types
    assert EventType.VOLUME_SPIKE in detected_types
    assert len(events) == 3


@pytest.mark.anyio
@patch("yfinance.Ticker")
async def test_market_trigger_error_handling(mock_ticker_class: MagicMock) -> None:
    """Test graceful recovery when a yfinance call fails."""
    mock_ticker_class.side_effect = Exception("Yahoo is down")

    service = MarketTriggerService()
    events = await service.scan_watchlist(["AAPL"])

    # Should handle error gracefully and return empty events list
    assert events == []


# ──────────────────────────────────────────────────────────────────────────────
# RAG Retrieval Layer Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@patch("src.services.market_insights.rag_client.WeaviateService")
async def test_rag_retrieval(mock_weaviate_class: MagicMock) -> None:
    """Test standard semantic context retrieval for an event."""
    mock_weaviate = MagicMock()
    mock_result_1 = MagicMock()
    mock_result_1.score = 0.85
    mock_result_1.model_dump.return_value = {
        "content": "Analyst downgrades AAPL to Sell on macro risk.",
        "score": 0.85,
    }
    mock_result_2 = MagicMock()
    mock_result_2.score = 0.20  # below relevance threshold

    mock_weaviate.search_similar = AsyncMock(
        return_value=[mock_result_1, mock_result_2]
    )
    mock_weaviate_class.return_value = mock_weaviate

    client = MarketInsightsRAGClient()
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_DROP,
        current_price=150.0,
        price_change_pct=-6.5,
    )

    chunks = await client.get_recent_context(event)
    assert len(chunks) == 1
    assert chunks[0]["score"] == 0.85
    assert "downgrades AAPL" in chunks[0]["content"]


# ──────────────────────────────────────────────────────────────────────────────
# LLM Engine Layer Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@patch("src.services.market_insights.llm_engine.FallbackAsyncOpenAI")
async def test_llm_classification_success(mock_openai_class: MagicMock) -> None:
    """Test standard 30-topic classification via LLM engine."""
    mock_completion = MagicMock()
    mock_message = MagicMock()
    mock_output = MagicMock()
    mock_output.category = InsightCategory.PRICE_ACTION
    mock_output.topic = InsightTopic.INTRADAY_DROP
    mock_output.confidence = 0.95
    mock_output.summary = "Apple shares tumble 6% on high volume."
    mock_output.context_insufficient = False

    mock_message.parsed = mock_output
    mock_completion.choices = [MagicMock(message=mock_message)]

    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)
    mock_openai_class.return_value = mock_client

    engine = LLMEngine()
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_DROP,
        current_price=150.0,
        price_change_pct=-6.0,
    )

    result = await engine.classify_event(event, [{"content": "Downgrade AAPL", "score": 0.8}])
    assert result.category == InsightCategory.PRICE_ACTION
    assert result.topic == InsightTopic.INTRADAY_DROP
    assert result.confidence == 0.95
    assert not result.fallback_used


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher Layer Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dispatcher_deduplication() -> None:
    """Test TTL-based alert deduplication logic."""
    mock_redis = AsyncMock()
    # First call: not a duplicate (exists returns 0)
    # Second call: is a duplicate (exists returns 1)
    mock_redis.exists.side_effect = [0, 1]
    mock_redis.get.return_value = "0"  # daily send count = 0

    dispatcher = NotificationDispatcher(redis_client=mock_redis)
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_DROP,
        current_price=150.0,
        price_change_pct=-6.0,
    )
    insight = InsightResult(
        event=event,
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.INTRADAY_DROP,
        confidence=0.9,
        summary="Apple drop.",
    )

    # First dispatch should succeed
    alert_1 = await dispatcher.dispatch(insight, "user_123", 3)
    assert alert_1 is not None

    # Second dispatch should trigger deduplication and return None
    alert_2 = await dispatcher.dispatch(insight, "user_123", 3)
    assert alert_2 is None


@pytest.mark.anyio
async def test_dispatcher_tier_entitlement() -> None:
    """Test daily cap enforcement for premium tiers and weekly summary for basic tiers."""
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = 0  # not duplicate
    mock_redis.get.return_value = "5"  # daily send limit reached for user

    dispatcher = NotificationDispatcher(redis_client=mock_redis)
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_DROP,
        current_price=150.0,
        price_change_pct=-6.0,
    )
    insight = InsightResult(
        event=event,
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.INTRADAY_DROP,
        confidence=0.9,
        summary="Apple drop.",
    )

    # Tier 3 (Premium) user over limit should be dropped
    alert_premium = await dispatcher.dispatch(insight, "user_premium", 3)
    assert alert_premium is None

    # Tier 2 (Basic) user under weekly accumulator should still succeed (no daily cap)
    alert_basic = await dispatcher.dispatch(insight, "user_basic", 2)
    assert alert_basic is not None
    assert not alert_basic.is_immediate
