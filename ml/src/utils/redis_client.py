"""Redis client helpers."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import redis
import redis.asyncio as redis_async

from config.settings import settings


def _redis_client_kwargs() -> dict[str, Any]:
    """Build Redis client options with production-friendly timeouts."""
    return {
        "socket_connect_timeout": settings.redis_socket_connect_timeout_seconds,
        "socket_timeout": settings.redis_socket_timeout_seconds,
        "health_check_interval": settings.redis_health_check_interval_seconds,
        "retry_on_timeout": True,
        "max_connections": settings.redis_max_connections,
    }


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis[str]:
    """Get or create the synchronous Redis client singleton."""
    return redis.from_url(
        settings.redis_url, decode_responses=True, **_redis_client_kwargs()
    )


_async_redis_client: redis_async.Redis[str] | None = None
_async_redis_loop: asyncio.AbstractEventLoop | None = None


def get_async_redis() -> redis_async.Redis[str]:
    """Get or create the asynchronous Redis client singleton.

    This uses a loop-aware cache: if the running event loop is closed
    or has changed, it will instantiate a new Redis client singleton.
    """
    global _async_redis_client, _async_redis_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _async_redis_client is not None:
        if (
            _async_redis_loop is None
            or _async_redis_loop.is_closed()
            or (current_loop is not None and _async_redis_loop is not current_loop)
        ):
            _async_redis_client = None
            _async_redis_loop = None

    if _async_redis_client is None:
        _async_redis_client = redis_async.from_url(
            settings.redis_url, decode_responses=True, **_redis_client_kwargs()
        )
        _async_redis_loop = current_loop

    return _async_redis_client
