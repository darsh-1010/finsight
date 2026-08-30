"""Quota enforcement middleware."""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from config.settings import settings
from src.core.tier_feature_resolver import resolver
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)


class QuotaMiddleware(BaseHTTPMiddleware):
    """Enforces daily request quotas based on user tier."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and enforce quota."""
        if not settings.tier_enforcement_enabled:
            return await call_next(request)

        # Only enforce on chat/upload/research endpoints
        path = request.url.path
        if not (
            path.startswith("/api/v1/chat")
            or path.startswith("/api/v1/upload")
            or path.startswith("/api/v1/research")
        ):
            return await call_next(request)

        user_id = self._get_user_id(request)
        if not user_id:
            return await call_next(request)

        # Resolve tier features
        tier_id = self._get_tier_id(request)
        # Note: Resolver handles caching and overrides
        features = await resolver.resolve(tier_id)

        # Check Daily Quota (Redis-backed windowed counter)
        if features.quota_daily_requests > 0:
            is_allowed = await self._check_quota(user_id, features.quota_daily_requests)
            if not is_allowed:
                logger.warning(
                    "[QUOTA_EXCEEDED] User: %s | Tier: %d | Limit: %d",
                    user_id,
                    tier_id,
                    features.quota_daily_requests,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Daily request quota exceeded for your tier.",
                        "limit": features.quota_daily_requests,
                    },
                )

        return await call_next(request)

    def _get_user_id(self, request: Request) -> str | None:
        """Extract user_id from headers."""
        return request.headers.get("x-user-id")

    def _get_tier_id(self, request: Request) -> int:
        """Extract tier_id from headers, default to 1."""
        try:
            return int(request.headers.get("x-tier-id", "1"))
        except (ValueError, TypeError):
            return 1

    async def _check_quota(self, user_id: str, limit: int) -> bool:
        """Check if user is within their daily quota using Redis."""
        redis = get_async_redis()
        # Daily bucket key (YYYY-MM-DD format)
        day_key = time.strftime("%Y-%m-%d")
        key = f"quota:{user_id}:{day_key}"

        try:
            count = await redis.incr(key)
            if count == 1:
                # Set TTL for 25 hours to clear old data
                await redis.expire(key, 90000)

            return count <= limit
        except ConnectionError as exc:
            # Safely fail-open if Redis is down
            logger.error("[QUOTA_REDIS_ERROR] %s", exc)
            return True
