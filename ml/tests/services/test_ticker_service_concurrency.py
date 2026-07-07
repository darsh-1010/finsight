"""Tests for bounded ticker resolution concurrency."""

import asyncio
from types import SimpleNamespace

import pytest

from src.services import ticker_service
from src.services.ticker_service import TickerService


class FakeRedisClient:
    """Minimal Redis double for ticker cache operations."""

    def get(self, key: str) -> None:
        return None

    def setex(self, key: str, ttl: int, value: str) -> None:
        return None


class FakePrompt:
    """Return a fake runnable chain that emits deterministic JSON."""

    def __init__(self, fake_chain: object):
        self._fake_chain = fake_chain

    def __or__(self, other: object) -> object:
        return self._fake_chain


class FakeChain:
    """Track concurrent LLM work without calling a real model."""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def ainvoke(self, payload: dict[str, str]) -> SimpleNamespace:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.05)
            return SimpleNamespace(
                content=(
                    '{"company_name":"Apple","ticker":"AAPL","confidence":0.9,'
                    '"exchange":"NASDAQ","alternatives":[]}'
                )
            )
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_ticker_resolution_is_bounded(monkeypatch):
    """Ticker resolution should honor the configured concurrency cap."""
    fake_chain = FakeChain()
    fake_redis = FakeRedisClient()

    async def fake_to_thread(function: object, *args: object) -> object:
        return function(*args)

    monkeypatch.setattr(ticker_service, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(ticker_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(ticker_service.PromptLoader, "load", lambda _: "prompt")

    service = TickerService(llm=object(), validate_tickers=False)
    service._prompt = FakePrompt(fake_chain)
    service._resolution_semaphore = asyncio.Semaphore(1)

    results = await asyncio.gather(
        service.resolve("QuantCorpAlpha"),
        service.resolve("QuantCorpBeta"),
    )

    assert fake_chain.max_active == 1
    assert results[0]["ticker"] == "AAPL"
    assert results[1]["ticker"] == "AAPL"
