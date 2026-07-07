"""Tests for the yFinance data source transport configuration."""

import asyncio
from types import SimpleNamespace

import pytest

from src.data_sources import yfinance_source
from src.data_sources.yfinance_source import YFinanceDataSource


def test_build_ticker_uses_shared_browser_session(monkeypatch):
    """The ticker factory should reuse one browser-impersonated session."""
    created_sessions = []
    created_tickers = []

    class FakeSession:
        """Capture session constructor arguments."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created_sessions.append(self)

    def fake_ticker(symbol, session=None):
        created_tickers.append({"symbol": symbol, "session": session})
        return {"symbol": symbol, "session": session}

    monkeypatch.setattr(yfinance_source, "CurlCffiSession", FakeSession)
    monkeypatch.setattr(yfinance_source.yf, "Ticker", fake_ticker)
    monkeypatch.setattr(
        yfinance_source.settings,
        "yfinance_use_browser_session",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        yfinance_source.settings,
        "yfinance_impersonate",
        "chrome",
        raising=False,
    )
    monkeypatch.setattr(
        yfinance_source.settings,
        "yfinance_http_timeout_seconds",
        12,
        raising=False,
    )

    data_source = YFinanceDataSource()
    first_ticker = data_source._build_ticker("AAPL")
    second_ticker = data_source._build_ticker("MSFT")

    assert len(created_sessions) == 1
    assert created_tickers[0]["session"] is created_tickers[1]["session"]
    assert created_sessions[0].kwargs == {"impersonate": "chrome", "timeout": 12}
    assert first_ticker["session"] is second_ticker["session"]


def test_build_ticker_falls_back_without_curl_cffi(monkeypatch):
    """The ticker factory should fall back to default yfinance transport."""
    created_tickers = []

    def fake_ticker(symbol, session=None):
        created_tickers.append({"symbol": symbol, "session": session})
        return {"symbol": symbol, "session": session}

    monkeypatch.setattr(yfinance_source, "CurlCffiSession", None)
    monkeypatch.setattr(yfinance_source.yf, "Ticker", fake_ticker)
    monkeypatch.setattr(
        yfinance_source.settings,
        "yfinance_use_browser_session",
        True,
        raising=False,
    )

    data_source = YFinanceDataSource()
    ticker = data_source._build_ticker("AAPL")

    assert created_tickers == [{"symbol": "AAPL", "session": None}]
    assert ticker["session"] is None


@pytest.mark.asyncio
async def test_yfinance_work_is_bounded_by_semaphore(monkeypatch):
    """The data source should cap concurrent yFinance work."""
    data_source = YFinanceDataSource()
    data_source._fetch_semaphore = asyncio.Semaphore(1)

    class FakeLoop:
        """Track concurrent executor work without using real threads."""

        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def run_in_executor(self, executor, function, *args):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(0.05)
                return function(*args)
            finally:
                self.active -= 1

    fake_loop = FakeLoop()
    monkeypatch.setattr(yfinance_source.asyncio, "get_running_loop", lambda: fake_loop)

    results = await asyncio.gather(
        data_source._run_with_limit(lambda: "one"),
        data_source._run_with_limit(lambda: "two"),
    )

    assert results == ["one", "two"]
    assert fake_loop.max_active == 1


@pytest.mark.asyncio
async def test_get_real_time_price_uses_ticker_builder(monkeypatch):
    """Real-time price fetches should use the shared ticker builder."""
    data_source = YFinanceDataSource()
    built_symbols = []

    class FakeLoop:
        """Run executor work inline so the test does not leave worker threads behind."""

        async def run_in_executor(self, executor, function, *args):
            return function(*args)

    def fake_build_ticker(symbol):
        built_symbols.append(symbol)
        return SimpleNamespace(
            info={
                "currentPrice": 123.45,
                "regularMarketChange": 1.23,
                "regularMarketChangePercent": 1.0,
            }
        )

    monkeypatch.setattr(data_source, "_build_ticker", fake_build_ticker)
    monkeypatch.setattr(yfinance_source.asyncio, "get_running_loop", lambda: FakeLoop())

    result = await data_source.get_real_time_price("aapl")

    assert built_symbols == ["AAPL"]
    assert result["ticker"] == "AAPL"
    assert result["price"] == 123.45
