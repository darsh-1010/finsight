"""Comprehensive edge-case unit and integration tests for the Market Insights API.

Validates the system's resilience against extremely messy inputs, penny stocks,
empty averages, Weaviate dropouts, and generic OpenAI HTTP/rate-limiting failures.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import LLMError, RAGError, YFinanceError
from src.services.market_insights.llm_engine import LLMEngine
from src.services.market_insights.market_triggers import MarketTriggerService
from src.services.market_insights.models import EventType, MarketEvent
from src.services.market_insights.rag_client import MarketInsightsRAGClient


@pytest.mark.anyio
async def test_edge_case_penny_stocks_zero_volume() -> None:
    """Edge Case: Stock has 0 trading volume or average volume is 0/None.

    Ensures that _check_volume_spike handles division-by-zero or empty averages
    completely gracefully, and successfully defaults to STANDARD_UPDATE.
    """
    service = MarketTriggerService()
    
    # 0 volume
    data_zero_vol = {
        "price": 1.50,
        "open": 1.50,
        "week_52_high": 5.00,
        "week_52_low": 1.00,
        "volume": 0,
        "avg_volume": 100000
    }
    events = service._detect_events("PENY", data_zero_vol)
    assert len(events) == 1
    assert events[0].event_type == EventType.STANDARD_UPDATE

    # 0 average volume (division-by-zero risk)
    data_zero_avg = {
        "price": 1.50,
        "open": 1.50,
        "week_52_high": 5.00,
        "week_52_low": 1.00,
        "volume": 50000,
        "avg_volume": 0
    }
    events = service._detect_events("PENY", data_zero_avg)
    assert len(events) == 1
    assert events[0].event_type == EventType.STANDARD_UPDATE

    # None average volume
    data_none_avg = {
        "price": 1.50,
        "open": 1.50,
        "week_52_high": 5.00,
        "week_52_low": 1.00,
        "volume": 50000,
        "avg_volume": None
    }
    events = service._detect_events("PENY", data_none_avg)
    assert len(events) == 1
    assert events[0].event_type == EventType.STANDARD_UPDATE


@pytest.mark.anyio
@patch("src.services.market_insights.market_triggers.yf.Ticker")
async def test_edge_case_malformed_yfinance_price(mock_ticker_class: MagicMock) -> None:
    """Edge Case: Ticker data does not have price field at all.

    Ensures that when price data is completely missing or is None/0,
    the trigger service skips detecting events and logs it cleanly instead of crashing.
    """
    mock_stock = MagicMock()
    # Return empty dict for info
    type(mock_stock).info = property(lambda self: {})
    # Return empty fast_info
    type(mock_stock).fast_info = property(lambda self: {})
    mock_ticker_class.return_value = mock_stock

    service = MarketTriggerService()
    
    with pytest.raises(YFinanceError):
        # Should raise YFinanceError because no price can be resolved
        service._fetch_ticker_data("VOID")


@pytest.mark.anyio
@patch("src.services.market_insights.rag_client.WeaviateService")
async def test_edge_case_vector_db_timeout_or_dns_failure(mock_weaviate_service_class: MagicMock) -> None:
    """Edge Case: Weaviate vector service suffers a socket timeout or DNS lookup failure.

    Verifies that search_similar raising a raw socket/runtime exception is caught cleanly,
    returning an empty chunk list [] instead of crashing.
    """
    mock_vector = mock_weaviate_service_class.return_value
    mock_vector.search_similar = AsyncMock(side_effect=TimeoutError("Connection timed out"))

    client = MarketInsightsRAGClient()
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.STANDARD_UPDATE,
        current_price=180.0,
        price_change_pct=0.0,
    )

    chunks = await client.get_recent_context(event)
    assert chunks == []


@pytest.mark.anyio
@patch("src.services.market_insights.llm_engine.get_structured_llm_client")
async def test_edge_case_openai_connection_and_ratelimit_errors(mock_get_client: MagicMock) -> None:
    """Edge Case: OpenAI API returns direct rate limit or connection drops.

    Verifies that our enhanced catch-all handler cleanly maps unhandled generic exceptions
    to an LLMError (which is a subclass of AppError).
    """
    mock_client = mock_get_client.return_value
    # Simulate a network/API rate limit error not covered by (ValueError, AttributeError, RuntimeError)
    mock_client.beta.chat.completions.parse = AsyncMock(
        side_effect=Exception("HTTP 429 Too Many Requests: Rate Limit Exceeded")
    )

    engine = LLMEngine()
    event = MarketEvent(
        ticker="AAPL",
        event_type=EventType.STANDARD_UPDATE,
        current_price=180.0,
        price_change_pct=0.0,
    )

    with pytest.raises(LLMError) as exc_info:
        await engine.classify_event(event, [])
    
    assert "LLM classification failed" in str(exc_info.value)
    assert "Rate Limit" in str(exc_info.value)


@pytest.mark.anyio
@patch("src.api.routes.market_insights.MarketTriggerService")
@patch("src.api.routes.market_insights.MarketInsightsRAGClient")
@patch("src.api.routes.market_insights.LLMEngine")
@patch("src.api.routes.market_insights.build_dispatcher")
async def test_edge_case_entire_scan_route_resilience_to_crashes(
    mock_build_dispatcher: MagicMock,
    mock_llm_engine_class: MagicMock,
    mock_rag_client_class: MagicMock,
    mock_trigger_service_class: MagicMock,
) -> None:
    """Integration Edge Case: A ticker classification fails with a raw exception in the routes loop.

    Ensures that if one ticker classification fails unexpectedly inside the loop,
    the api scan route catches the exception, logs it, and continues scanning
    the other tickers in the watchlist instead of throwing a 500 error.
    """
    from src.api.routes.market_insights import scan_watchlist
    from src.services.market_insights.models import ScanRequest

    # Set up mocks
    mock_trigger = mock_trigger_service_class.return_value
    mock_rag = mock_rag_client_class.return_value
    mock_llm = mock_llm_engine_class.return_value
    mock_disp = mock_build_dispatcher.return_value

    # We scan 2 tickers: AAPL (which will raise exception) and TSLA (which succeeds)
    event_aapl = MarketEvent(ticker="AAPL", event_type=EventType.STANDARD_UPDATE, current_price=180.0, price_change_pct=0.0)
    event_tsla = MarketEvent(ticker="TSLA", event_type=EventType.STANDARD_UPDATE, current_price=200.0, price_change_pct=0.0)
    
    mock_trigger.scan_watchlist = AsyncMock(return_value=[event_aapl, event_tsla])
    mock_rag.get_recent_context = AsyncMock(return_value=[])

    # Mock classify_event to fail on AAPL but succeed on TSLA
    async def side_effect_classify(event, chunks):
        if event.ticker == "AAPL":
            raise Exception("Unexpected LLM server crash")
        
        from src.services.market_insights.models import (InsightCategory,
                                                         InsightResult,
                                                         InsightTopic)
        return InsightResult(
            event=event,
            category=InsightCategory.PRICE_ACTION,
            topic=InsightTopic.INTRADAY_DROP,
            confidence=0.95,
            summary="Slight intraday drop for Tesla",
        )
    
    mock_llm.classify_event = AsyncMock(side_effect=side_effect_classify)
    mock_disp.dispatch = AsyncMock(return_value=None)

    request = ScanRequest(
        user_id="usr_999",
        user_tier=2,
        tickers=["AAPL", "TSLA"]
    )

    # Invoke scan_watchlist API router directly, passing mock dependencies explicitly
    from tests.api.test_market_insights_endpoints import MockTickerService
    response = await scan_watchlist(
        request=request,
        ticker_service=MockTickerService(),
        dispatcher=mock_disp,
    )

    # AAPL failed but TSLA succeeded, so length resolved is 2, scanned is 2
    assert response.scanned == 2
    assert response.events_detected == 2
    # Only TSLA insight is returned in response list since AAPL was skipped cleanly
    assert len(response.insights) == 1
