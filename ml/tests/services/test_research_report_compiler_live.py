"""Live-network integration test for the Research Report Compiler.

Unlike test_research_report_compiler.py (fully mocked), this hits the REAL
yfinance and SEC EDGAR APIs for a well-known, stable ticker to prove the two
external data integrations actually work end to end. Only the LLM call is
mocked (no API credentials needed for this test).

Skipped automatically if there's no network access.
"""

import socket
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.schemas import ResearchReportLLMOutput
from src.services.research.report_compiler import ResearchReportCompiler


def _has_network() -> bool:
    try:
        socket.create_connection(("query1.finance.yahoo.com", 443), timeout=3).close()
        return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _has_network(), reason="No network access to Yahoo Finance"
)


def _make_openai_mock():
    parsed = ResearchReportLLMOutput(
        summary="Test summary.",
        valuation_take="Test valuation.",
        growth_take="Test growth.",
        risk_take="Test risk.",
        filing_highlights=["Test highlight."],
    )
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(parsed=parsed))]

    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(return_value=completion)
    return client


@requires_network
@pytest.mark.asyncio
async def test_real_yfinance_and_edgar_for_aapl():
    """AAPL should resolve real fundamentals and a real 10-K filing excerpt."""
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)

    compiler = ResearchReportCompiler(
        openai_client=_make_openai_mock(), redis_client=redis_client
    )

    report = await compiler.get_or_generate_report("AAPL")

    assert report.ticker == "AAPL"
    assert report.company_name and "Apple" in report.company_name
    assert report.financial_context is not None
    assert report.financial_context["current_price"] > 0

    # AAPL has always filed 10-Ks; a real filing source should be present.
    source_types = {s.source_type for s in report.sources}
    assert "yfinance" in source_types
    assert "sec_filing" in source_types


@requires_network
@pytest.mark.asyncio
async def test_real_yfinance_invalid_ticker_raises():
    """A nonsense ticker should raise YFinanceError, not silently succeed."""
    from src.core.exceptions import YFinanceError

    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)

    compiler = ResearchReportCompiler(
        openai_client=_make_openai_mock(), redis_client=redis_client
    )

    with pytest.raises(YFinanceError):
        await compiler.get_or_generate_report("ZZZZZINVALIDTICKER")
