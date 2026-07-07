"""Rate limiting utilities for API calls."""

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


class RateLimitError(Exception):
    """Raised when a request exceeds the configured rate limit."""

    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class RateLimiter:
    """Redis-backed fixed-window rate limiter with a local fallback."""

    def __init__(
        self,
        requests_per_minute: int | None = None,
        tokens_per_minute: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.requests_per_minute = requests_per_minute or settings.rate_limit_rpm
        self.tokens_per_minute = tokens_per_minute or settings.rate_limit_tpm
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self._redis = get_async_redis()
        self._redis_lock = asyncio.Lock()
        self._local_lock = asyncio.Lock()
        self._local_request_hits: dict[str, list[float]] = {}
        self._local_token_hits: dict[str, list[tuple[float, int]]] = {}

    def _make_bucket_key(self, identifier: str, route: str) -> str:
        """Create a stable Redis key without storing raw client identifiers."""
        digest = hashlib.sha256(f"{route}:{identifier}".encode()).hexdigest()[
            :24
        ]
        return f"rate_limit:{route}:{digest}"

    async def acquire(
        self, identifier: str, tokens: int = 0, route: str = "chat"
    ) -> None:
        """Acquire permission to make a request or raise immediately."""
        normalized_identifier = identifier.strip() or "anonymous"
        try:
            if await self._acquire_with_redis(normalized_identifier, route, tokens):
                return
        except RateLimitError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via fallback path
            logger.warning(
                "[RATE_LIMIT] Redis limiter unavailable, using local fallback: %s", exc
            )

        await self._acquire_with_local_state(normalized_identifier, route, tokens)

    async def _acquire_with_redis(
        self, identifier: str, route: str, tokens: int
    ) -> bool:
        """Try to enforce the limit with Redis and return True on success."""
        async with self._redis_lock:
            try:
                request_key = self._make_bucket_key(identifier, route)
                request_count = await self._redis.incr(request_key)
                if request_count == 1:
                    await self._redis.expire(request_key, self.window_seconds)

                if request_count > self.requests_per_minute:
                    ttl = await self._redis.ttl(request_key)
                    retry_after = ttl if ttl and ttl > 0 else self.window_seconds
                    raise RateLimitError(
                        "Rate limit exceeded",
                        retry_after_seconds=retry_after,
                    )

                if tokens > 0:
                    token_key = f"{request_key}:tokens"
                    token_count = await self._redis.incrby(token_key, tokens)
                    if token_count == tokens:
                        await self._redis.expire(token_key, self.window_seconds)
                    if token_count > self.tokens_per_minute:
                        ttl = await self._redis.ttl(token_key)
                        retry_after = ttl if ttl and ttl > 0 else self.window_seconds
                        raise RateLimitError(
                            "Token limit exceeded",
                            retry_after_seconds=retry_after,
                        )

                return True
            except RateLimitError:
                raise
            except Exception:
                return False

    async def _acquire_with_local_state(
        self, identifier: str, route: str, tokens: int
    ) -> None:
        """Enforce the limit with in-memory state if Redis is unavailable."""
        async with self._local_lock:
            now = time.time()
            cutoff = now - self.window_seconds
            request_key = self._make_bucket_key(identifier, route)

            self._local_request_hits[request_key] = [
                timestamp
                for timestamp in self._local_request_hits.get(request_key, [])
                if timestamp > cutoff
            ]
            if len(self._local_request_hits[request_key]) >= self.requests_per_minute:
                retry_after = self.window_seconds - int(
                    now - self._local_request_hits[request_key][0]
                )
                raise RateLimitError(
                    "Rate limit exceeded", retry_after_seconds=max(retry_after, 1)
                )

            self._local_request_hits[request_key].append(now)

            if tokens <= 0:
                return

            self._local_token_hits[request_key] = [
                (timestamp, count)
                for timestamp, count in self._local_token_hits.get(request_key, [])
                if timestamp > cutoff
            ]
            current_tokens = sum(
                count for _, count in self._local_token_hits[request_key]
            )
            if current_tokens + tokens > self.tokens_per_minute:
                retry_after = self.window_seconds - int(
                    now - self._local_token_hits[request_key][0][0]
                )
                raise RateLimitError(
                    "Token limit exceeded", retry_after_seconds=max(retry_after, 1)
                )

            self._local_token_hits[request_key].append((now, tokens))


def with_retry(
    max_attempts: int | None = None,
    initial_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float = 2.0,
):
    """Decorator for retrying async functions with exponential backoff."""
    max_attempts = max_attempts or settings.max_retries
    initial_delay = initial_delay or settings.retry_initial_delay
    max_delay = max_delay or settings.retry_max_delay

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=initial_delay,
                max=max_delay,
                exp_base=exponential_base,
            ),
            retry=retry_if_exception_type((ConnectionError,)),
            reraise=True,
        )
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await func(*args, **kwargs)

        return wrapper

    return decorator
