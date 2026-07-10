"""
Unit tests for the ML service rate limiter.

Tests the local in-memory fallback path (no Redis required).
All tests run fully offline.
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src and root are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def rate_limiter():
    """
    Returns a RateLimiter instance with a mocked Redis that always fails,
    forcing the local-state fallback path under test.
    """
    from src.utils.rate_limiter import RateLimiter

    mock_redis = AsyncMock()
    # Simulate Redis being unavailable so local fallback is always exercised
    mock_redis.incr.side_effect = ConnectionError("Redis unavailable")
    mock_redis.expire.side_effect = ConnectionError("Redis unavailable")

    with patch("src.utils.rate_limiter.get_async_redis", return_value=mock_redis):
        limiter = RateLimiter(
            requests_per_minute=5,
            tokens_per_minute=1000,
            window_seconds=60,
        )
        # Inject the mock directly so _redis_lock operations use it
        limiter._redis = mock_redis
        yield limiter


@pytest.fixture
def redis_rate_limiter():
    """
    Returns a RateLimiter backed by a fully mocked functional Redis.
    Used for testing the Redis-backed path.
    """
    from src.utils.rate_limiter import RateLimiter

    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)  # First request always count=1
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.ttl = AsyncMock(return_value=55)

    with patch("src.utils.rate_limiter.get_async_redis", return_value=mock_redis):
        limiter = RateLimiter(
            requests_per_minute=10,
            tokens_per_minute=5000,
            window_seconds=60,
        )
        limiter._redis = mock_redis
        yield limiter


# ── RateLimitError ────────────────────────────────────────────────────────────

class TestRateLimitError:
    """Unit tests for the RateLimitError exception class."""

    def test_is_exception(self):
        """RateLimitError must be an Exception subclass."""
        from src.utils.rate_limiter import RateLimitError
        assert issubclass(RateLimitError, Exception)

    def test_message_stored(self):
        """Constructor message must be retrievable."""
        from src.utils.rate_limiter import RateLimitError
        exc = RateLimitError("Rate limit exceeded", retry_after_seconds=30)
        assert exc.message == "Rate limit exceeded"

    def test_retry_after_stored(self):
        """retry_after_seconds must be stored on the exception."""
        from src.utils.rate_limiter import RateLimitError
        exc = RateLimitError("Limit hit", retry_after_seconds=45)
        assert exc.retry_after_seconds == 45

    def test_retry_after_defaults_to_none(self):
        """retry_after_seconds defaults to None if not provided."""
        from src.utils.rate_limiter import RateLimitError
        exc = RateLimitError("Limit hit")
        assert exc.retry_after_seconds is None


# ── Local fallback path ───────────────────────────────────────────────────────

class TestRateLimiterLocalFallback:
    """Tests for the in-memory (local) rate limiting path."""

    def test_acquire_within_limit_does_not_raise(self, rate_limiter):
        """Requests within the limit must not raise."""
        async def run():
            await rate_limiter.acquire("user_1", route="/api/v1/chat")

        asyncio.get_event_loop().run_until_complete(run())

    def test_acquire_exceeds_rpm_raises_rate_limit_error(self, rate_limiter):
        """After exceeding requests_per_minute, RateLimitError must be raised."""
        from src.utils.rate_limiter import RateLimitError

        async def run():
            for _ in range(5):  # exhaust the limit
                await rate_limiter.acquire("user_burst", route="/api/v1/chat/msg")
            # This one should fail
            await rate_limiter.acquire("user_burst", route="/api/v1/chat/msg")

        with pytest.raises(RateLimitError):
            asyncio.get_event_loop().run_until_complete(run())

    def test_rate_limit_error_has_retry_after(self, rate_limiter):
        """RateLimitError raised from local path must include retry_after_seconds."""
        from src.utils.rate_limiter import RateLimitError

        async def run():
            for _ in range(5):
                await rate_limiter.acquire("user_retry", route="/api/v1/chat/stream")
            await rate_limiter.acquire("user_retry", route="/api/v1/chat/stream")

        with pytest.raises(RateLimitError) as exc_info:
            asyncio.get_event_loop().run_until_complete(run())

        assert exc_info.value.retry_after_seconds is not None
        assert exc_info.value.retry_after_seconds >= 1

    def test_different_identifiers_are_isolated(self, rate_limiter):
        """Rate limits must be isolated per identifier (user)."""
        from src.utils.rate_limiter import RateLimitError

        async def run():
            # Fill up user A's quota
            for _ in range(5):
                await rate_limiter.acquire("user_a", route="/api/v1/chat/q")
            # user B must still be able to make a request
            await rate_limiter.acquire("user_b", route="/api/v1/chat/q")

        # Should not raise — user_b has not hit their limit
        asyncio.get_event_loop().run_until_complete(run())

    def test_token_limit_enforced(self, rate_limiter):
        """Token quota must be enforced when accumulated token usage exceeds the limit."""
        from src.utils.rate_limiter import RateLimitError

        async def run():
            # Accumulate tokens across requests: 6 * 200 = 1200 > tokens_per_minute (1000)
            for _ in range(6):
                await rate_limiter.acquire("user_toks", tokens=200, route="/api/v1/chat/tok")

        with pytest.raises(RateLimitError):
            asyncio.get_event_loop().run_until_complete(run())


# ── Redis-backed path ─────────────────────────────────────────────────────────

class TestRateLimiterRedisPath:
    """Tests for the Redis-backed rate limiting path."""

    def test_redis_path_does_not_raise_within_limit(self, redis_rate_limiter):
        """When Redis count is within limit, acquire must not raise."""
        async def run():
            await redis_rate_limiter.acquire("user_ok", route="/api/v1/chat/ok")

        asyncio.get_event_loop().run_until_complete(run())

    def test_redis_path_raises_when_count_exceeds_limit(self):
        """When Redis returns count > requests_per_minute, RateLimitError raised."""
        from src.utils.rate_limiter import RateLimitError, RateLimiter

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=999)  # Always over limit
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.ttl = AsyncMock(return_value=30)

        with patch("src.utils.rate_limiter.get_async_redis", return_value=mock_redis):
            limiter = RateLimiter(requests_per_minute=10, tokens_per_minute=5000, window_seconds=60)
            limiter._redis = mock_redis

        async def run():
            await limiter.acquire("user_over", route="/api/v1/chat/over")

        with pytest.raises(RateLimitError):
            asyncio.get_event_loop().run_until_complete(run())


# ── Bucket key generation ─────────────────────────────────────────────────────

class TestBucketKeyGeneration:
    """Tests for _make_bucket_key to verify privacy properties."""

    def test_key_does_not_contain_raw_identifier(self, rate_limiter):
        """Generated key must not expose the raw identifier."""
        key = rate_limiter._make_bucket_key("sensitive_user_id_12345", "/api/v1/chat")
        assert "sensitive_user_id_12345" not in key

    def test_same_inputs_produce_same_key(self, rate_limiter):
        """Key generation must be deterministic."""
        key1 = rate_limiter._make_bucket_key("user_abc", "/api/v1/chat")
        key2 = rate_limiter._make_bucket_key("user_abc", "/api/v1/chat")
        assert key1 == key2

    def test_different_routes_produce_different_keys(self, rate_limiter):
        """Different routes must not share the same bucket key."""
        key_chat = rate_limiter._make_bucket_key("user_x", "/api/v1/chat")
        key_other = rate_limiter._make_bucket_key("user_x", "/api/v1/other")
        assert key_chat != key_other
