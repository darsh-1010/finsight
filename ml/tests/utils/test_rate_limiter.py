"""Tests for the Redis-backed rate limiter."""

import pytest

from src.utils import rate_limiter
from src.utils.rate_limiter import RateLimitError, RateLimiter


class FakeRedisClient:
    """Minimal async Redis double for rate-limiter tests."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def incrby(self, key: str, amount: int) -> int:
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        return self.expirations.get(key, 60)


@pytest.mark.asyncio
async def test_rate_limiter_rejects_second_request(monkeypatch):
    """The limiter should reject excess traffic immediately."""
    fake_redis = FakeRedisClient()
    monkeypatch.setattr(rate_limiter, "get_async_redis", lambda: fake_redis)

    limiter = RateLimiter(requests_per_minute=1, tokens_per_minute=10, window_seconds=60)

    await limiter.acquire("client-1", route="/api/v1/chat")

    with pytest.raises(RateLimitError) as exc_info:
        await limiter.acquire("client-1", route="/api/v1/chat")

    assert exc_info.value.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_rate_limiter_uses_token_budget(monkeypatch):
    """The limiter should also enforce token budgets when provided."""
    fake_redis = FakeRedisClient()
    monkeypatch.setattr(rate_limiter, "get_async_redis", lambda: fake_redis)

    limiter = RateLimiter(requests_per_minute=10, tokens_per_minute=5, window_seconds=60)

    await limiter.acquire("client-1", tokens=4, route="/api/v1/chat")

    with pytest.raises(RateLimitError):
        await limiter.acquire("client-1", tokens=2, route="/api/v1/chat")
