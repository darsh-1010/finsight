"""Tests that ticker resolution survives a Redis outage.

Reuses the fake-chain / fake-redis pattern from
test_ticker_service_concurrency.py.
"""

import asyncio
from types import SimpleNamespace

import pytest
import redis

from src.services import ticker_service
from src.services.ticker_service import TickerService


class UnavailableRedisClient:
    """Redis double that always raises ConnectionError, like a down Redis."""

    def get(self, key: str) -> None:
        raise redis.exceptions.ConnectionError("Connection refused")

    def setex(self, key: str, ttl: int, value: str) -> None:
        raise redis.exceptions.ConnectionError("Connection refused")


class FakePrompt:
    def __init__(self, fake_chain: object):
        self._fake_chain = fake_chain

    def __or__(self, other: object) -> object:
        return self._fake_chain


class FakeChain:
    async def ainvoke(self, payload: dict[str, str]) -> SimpleNamespace:
        return SimpleNamespace(
            content=(
                '{"company_name":"Apple","ticker":"AAPL","confidence":0.9,'
                '"exchange":"NASDAQ","alternatives":[]}'
            )
        )


@pytest.mark.asyncio
async def test_resolve_degrades_to_llm_when_redis_is_down(monkeypatch):
    """A Redis outage should fall through to LLM resolution, not crash."""
    fake_chain = FakeChain()
    unavailable_redis = UnavailableRedisClient()

    async def fake_to_thread(function: object, *args: object) -> object:
        return function(*args)

    monkeypatch.setattr(ticker_service, "get_redis", lambda: unavailable_redis)
    monkeypatch.setattr(ticker_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(ticker_service.PromptLoader, "load", lambda _: "prompt")

    service = TickerService(llm=object(), validate_tickers=False)
    service._prompt = FakePrompt(fake_chain)
    service._resolution_semaphore = asyncio.Semaphore(1)

    # A name that won't hit the static lookup, forcing the Redis-then-LLM path.
    result = await service.resolve("QuantCorpAlpha Unknown Holdings")

    assert result["ticker"] == "AAPL"
