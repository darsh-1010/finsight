"""Unit tests for the Weekly Summary Compiler service.

Tests cache retrieval, dynamic yFinance integration (replacing Tavily),
OpenAI structured outputs compilation with tier-specific models, and fallback mechanisms.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.services.market_insights.models import (AlertPayload, EventType,
                                                 InsightCategory,
                                                 InsightResult, InsightTopic,
                                                 MarketEvent,
                                                 WeeklyStockHighlight,
                                                 WeeklySummaryReport)
from src.services.market_insights.weekly_compiler import WeeklySummaryCompiler


@pytest.fixture
def anyio_backend():
    """Force anyio backend to use asyncio."""
    return "asyncio"


def get_sample_raw_alerts() -> list[AlertPayload]:
    """Generates mock aggregated raw alert payloads."""
    event_1 = MarketEvent(
        ticker="AAPL",
        event_type=EventType.INTRADAY_DROP,
        current_price=175.0,
        price_change_pct=-5.4,
    )
    insight_1 = InsightResult(
        event=event_1,
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.INTRADAY_DROP,
        confidence=0.92,
        summary="Apple drops 5.4% intraday.",
    )

    event_2 = MarketEvent(
        ticker="TSLA",
        event_type=EventType.VOLUME_SPIKE,
        current_price=220.0,
        price_change_pct=1.2,
    )
    insight_2 = InsightResult(
        event=event_2,
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.VOLUME_SPIKE,
        confidence=0.88,
        summary="Tesla volume spikes to 2.5x normal.",
    )

    return [
        AlertPayload(insight=insight_1, user_tier=2, user_id="user_123"),
        AlertPayload(insight=insight_2, user_tier=2, user_id="user_123"),
    ]


def get_sample_report() -> WeeklySummaryReport:
    """Generates a sample target WeeklySummaryReport."""
    highlight_aapl = WeeklyStockHighlight(
        ticker="AAPL",
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.INTRADAY_DROP,
        weekly_trend="Bearish",
        price_change_pct=-5.4,
        key_event="Intraday sell-off",
        verification_status="Verified",
        summary="Apple dropped on macro risk.",
        citations=["https://example.com/aapl"],
        alert_message="📉 Apple dips -5.4% — Stock falls on intraday sell-off.",
        insight_source="yfinance",
    )

    highlight_tsla = WeeklyStockHighlight(
        ticker="TSLA",
        category=InsightCategory.PRICE_ACTION,
        topic=InsightTopic.VOLUME_SPIKE,
        weekly_trend="Bullish",
        price_change_pct=1.2,
        key_event="Trading volume spike",
        verification_status="Verified",
        summary="Tesla volume spiked indicating high interest.",
        citations=["https://example.com/tsla"],
        alert_message="📈 Tesla rises +1.2% — Volume surges on high retail interest.",
        insight_source="websearch",
    )

    return WeeklySummaryReport(
        overall_sentiment="Markets saw high volatility with Apple dropping and Tesla volume surging.",
        highlights=[highlight_aapl, highlight_tsla],
        macro_factors=["High trading volume", "Intraday drops"],
        key_takeaway="Volatile market action suggests keeping a defensive posture."
    )


def get_mock_download_data(tickers: list[str]) -> pd.DataFrame:
    """Generates 40 rows of mock Close and Volume data for list of tickers."""
    columns = pd.MultiIndex.from_product([tickers, ["Close", "Volume"]])
    data_dict = {}
    for ticker in tickers:
        data_dict[(ticker, "Close")] = [180.0] * 40
        data_dict[(ticker, "Volume")] = [100000] * 40
    return pd.DataFrame(data_dict, columns=columns)


# ──────────────────────────────────────────────────────────────────────────────
# Caching Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_compiler_cache_hit() -> None:
    """Test that compiler returns cached report on a Redis cache hit."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = get_sample_report().model_dump_json()

    compiler = WeeklySummaryCompiler(redis_client=mock_redis)

    report = await compiler.get_or_generate_summary("user_123", [], user_tier=2)

    assert "Markets saw high volatility" in report.overall_sentiment
    assert len(report.highlights) == 2
    mock_redis.get.assert_called_once_with("mi:weekly_report:tier:2")


# ──────────────────────────────────────────────────────────────────────────────
# Compilation and Verification Success Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@patch("src.services.market_insights.weekly_compiler.yf.Ticker")
@patch("src.services.market_insights.weekly_compiler.yf.download")
async def test_compiler_compilation_success(
    mock_yf_download: MagicMock,
    mock_yf_ticker: MagicMock
) -> None:
    """Test cache miss compiles, fetches yFinance news and history, runs LLM, and caches result."""
    # 1. Mock Redis Client
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss

    # 2. Mock OpenAI Client
    mock_completion = MagicMock()
    mock_message = MagicMock()
    mock_message.parsed = get_sample_report()
    mock_completion.choices = [MagicMock(message=mock_message)]

    mock_openai_client = MagicMock()
    mock_openai_client.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)

    # Mock OpenAI Responses API (used by _fetch_websearch_events for web search)
    mock_web_search_response = MagicMock()
    mock_web_search_response.output_text = ""
    mock_web_search_response.output = []
    mock_openai_client.responses.create = AsyncMock(return_value=mock_web_search_response)

    compiler = WeeklySummaryCompiler(openai_client=mock_openai_client, redis_client=mock_redis)

    # Mock yFinance download MultiIndex DataFrame
    combined_tickers = getattr(compiler, "_SCANNING_UNIVERSE") + getattr(compiler, "_MACRO_UNIVERSE")
    mock_yf_download.return_value = get_mock_download_data(combined_tickers)

    # Mock Ticker news responses
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.news = [
        {
            "content": {
                "title": "Apple news",
                "publisher": "Bloomberg",
                "link": "https://example.com/aapl",
                "providerPublishTime": 1690000000
            }
        }
    ]
    mock_yf_ticker.return_value = mock_ticker_instance

    report = await compiler.generate_and_cache_summary("user_123", get_sample_raw_alerts(), user_tier=2)

    # 5. Assertions
    assert len(report.highlights) == 2
    assert report.highlights[0].ticker == "AAPL"
    assert report.highlights[0].insight_source == "yfinance"
    assert report.highlights[1].ticker == "TSLA"
    assert report.highlights[1].insight_source == "websearch"

    mock_redis.set.assert_called()
    # Key 0 is the lock set, key 1 is report cache set
    cache_key, cached_json = mock_redis.set.call_args_list[1][0]
    assert cache_key == "mi:weekly_report:tier:2"
    assert "overall_sentiment" in cached_json


# ──────────────────────────────────────────────────────────────────────────────
# Graceful Degradation / Fallback Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@patch("src.services.market_insights.weekly_compiler.yf.download")
async def test_compiler_llm_fallback(
    mock_yf_download: MagicMock
) -> None:
    """Test that compiler falls back to a clean, safe report on LLM failure."""
    # 1. Mock Redis Client
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss

    # 2. Mock yFinance to return empty DataFrame to trigger fallback
    mock_yf_download.return_value = pd.DataFrame()

    # 3. Mock OpenAI Client to raise error
    mock_openai_client = MagicMock()
    mock_openai_client.beta.chat.completions.parse.side_effect = RuntimeError("LLM timed out")

    compiler = WeeklySummaryCompiler(openai_client=mock_openai_client, redis_client=mock_redis)
    report = await compiler.generate_and_cache_summary("user_123", get_sample_raw_alerts(), user_tier=1)

    # 4. Assertions
    assert len(report.highlights) == 10  # Fallback default list has 10 tickers
    assert report.highlights[0].verification_status == "Unverified"

    mock_redis.set.assert_called()


# ──────────────────────────────────────────────────────────────────────────────
# Concurrency and Zero-Blocking Path Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_compiler_instant_fallback_on_cache_miss() -> None:
    """Test get_or_generate_summary returns fallback instantly and schedules compile."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss

    compiler = WeeklySummaryCompiler(redis_client=mock_redis)

    # Call the non-blocking cache miss path
    report = await compiler.get_or_generate_summary("user_123", [], user_tier=2)

    # Must return fallback report instantly
    assert len(report.highlights) == 10
    assert report.highlights[0].verification_status == "Unverified"
    assert report.highlights[0].alert_message == "AAPL — Weekly market tracking update."
    assert report.overall_sentiment == (
        "Market data compilation completed. Refer to individual alerts for daily changes."
    )


@pytest.mark.anyio
async def test_compiler_concurrency_lock_acquired() -> None:
    """Test that concurrent calls to generate_and_cache_summary skip compilation."""
    mock_redis = AsyncMock()
    # Mock set NX to return False (lock already held by another worker)
    mock_redis.set.return_value = False

    compiler = WeeklySummaryCompiler(redis_client=mock_redis)

    # Calling generate_and_cache_summary must return None (skipped)
    report = await compiler.generate_and_cache_summary("user_123", [], user_tier=2)
    assert report is None
    mock_redis.set.assert_called_once_with("mi:weekly_report:lock:tier:2", "locked", ex=180, nx=True)
