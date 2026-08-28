"""Unit tests for the Research Report Compiler.

Tests cache hit/miss, graceful degradation when no SEC filing is found, and
that generated reports carry both yfinance and EDGAR sources when available.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.schemas import ResearchReportLLMOutput, ResearchReportResponse
from src.services.research.report_compiler import ResearchReportCompiler

_SAMPLE_YF_DATA = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "current_price": 227.5,
    "sector": "Technology",
    "pe_ratio": 32.1,
    "fetched_at": "2026-08-24T00:00:00Z",
}

_SAMPLE_LLM_OUTPUT = ResearchReportLLMOutput(
    summary="Apple is a large, stable technology company.",
    valuation_take="Trading at a premium multiple relative to the market.",
    growth_take="Services revenue continues to grow steadily.",
    risk_take="Heavy reliance on iPhone sales concentrates risk.",
    filing_highlights=["Revenue grew year over year.", "Services segment expanded."],
)


def _make_parse_mock(parsed=_SAMPLE_LLM_OUTPUT):
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(parsed=parsed))]
    return AsyncMock(return_value=completion)


@pytest.fixture
def mock_redis():
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    return redis_client


@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.beta.chat.completions.parse = _make_parse_mock()
    return client


@pytest.mark.asyncio
async def test_cache_hit_skips_regeneration(mock_redis, mock_openai_client):
    """A cached report should be returned without calling the LLM."""
    cached_report = ResearchReportResponse(
        ticker="AAPL",
        company_name="Apple Inc.",
        generated_at="2026-08-24T00:00:00Z",
        summary="cached summary",
        valuation_take="cached",
        growth_take="cached",
        risk_take="cached",
        sources=[],
        confidence=0.8,
        from_cache=False,
    )
    mock_redis.get = AsyncMock(return_value=cached_report.model_dump_json())

    compiler = ResearchReportCompiler(openai_client=mock_openai_client, redis_client=mock_redis)
    result = await compiler.get_or_generate_report("AAPL")

    assert result.summary == "cached summary"
    assert result.from_cache is True
    mock_openai_client.beta.chat.completions.parse.assert_not_called()


@pytest.mark.asyncio
async def test_generates_and_caches_report_with_filing(mock_redis, mock_openai_client):
    """A cache miss with an available 10-K should produce a report citing both sources."""
    compiler = ResearchReportCompiler(openai_client=mock_openai_client, redis_client=mock_redis)

    with patch(
        "src.services.research.report_compiler.YFinanceDataSource"
    ) as mock_yf_cls, patch(
        "src.services.research.report_compiler.EdgarSource"
    ) as mock_edgar_cls:
        mock_yf_cls.return_value.fetch = AsyncMock(return_value=_SAMPLE_YF_DATA)

        mock_edgar = mock_edgar_cls.return_value
        mock_edgar.get_filings = AsyncMock(
            return_value=[
                {
                    "primary_document_url": "https://sec.gov/filing.htm",
                    "accession_number": "0000320193-26-000001",
                }
            ]
        )
        mock_edgar.get_filing_text = AsyncMock(return_value="Apple's latest annual report text.")
        mock_edgar.close = AsyncMock()

        result = await compiler.get_or_generate_report("AAPL")

    assert result.ticker == "AAPL"
    assert result.company_name == "Apple Inc."
    assert result.from_cache is False
    assert len(result.sources) == 2
    source_types = {s.source_type for s in result.sources}
    assert source_types == {"yfinance", "sec_filing"}
    assert result.filing_highlights == _SAMPLE_LLM_OUTPUT.filing_highlights

    mock_redis.set.assert_awaited_once()
    cached_key, cached_value = mock_redis.set.call_args.args
    assert cached_key == "research:report:AAPL"
    assert json.loads(cached_value)["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_degrades_gracefully_without_filing(mock_redis, mock_openai_client):
    """A ticker with no 10-K on file should still produce a yfinance-only report."""
    compiler = ResearchReportCompiler(openai_client=mock_openai_client, redis_client=mock_redis)

    with patch(
        "src.services.research.report_compiler.YFinanceDataSource"
    ) as mock_yf_cls, patch(
        "src.services.research.report_compiler.EdgarSource"
    ) as mock_edgar_cls:
        mock_yf_cls.return_value.fetch = AsyncMock(return_value=_SAMPLE_YF_DATA)

        mock_edgar = mock_edgar_cls.return_value
        mock_edgar.get_filings = AsyncMock(return_value=[])
        mock_edgar.close = AsyncMock()

        result = await compiler.get_or_generate_report("AAPL")

    assert result.ticker == "AAPL"
    assert len(result.sources) == 1
    assert result.sources[0].source_type == "yfinance"
