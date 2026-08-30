"""Tier feature resolution logic (Trust but Verify)."""

import json
from typing import Any

import httpx

from config.settings import settings
from src.core.tier_policy import TierFeatures, get_static_policy
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)


class TierFeatureResolver:
    """Resolves tier features from overrides, cache, or backend API."""

    def __init__(self) -> None:
        """Initialize the resolver."""
        self.redis = get_async_redis()
        self.backend_url = f"{settings.ml_data_transfer_base_url}/api/v1/tier"

    async def resolve(
        self,
        tier_id: int,
        override_features: dict[str, Any] | None = None,
        override_tier_name: str | None = None,
    ) -> TierFeatures:
        """Resolve final feature set for a user tier.

        Priority:
        1. Request-level overrides (Internal/Fast-path)
        2. Redis Cache
        3. Backend API Call
        4. Static Fallback Policy
        """
        # 1. Fast-path: Trusted Internal Overrides
        if override_features:
            logger.info("[TIER_RESOLVE] Source: RequestOverride | Tier: %d", tier_id)
            normalized = self._normalize_feature_payload(override_features)
            return TierFeatures(
                name=override_tier_name or f"Tier {tier_id}",
                **normalized,
            )

        # 2. Redis Cache Lookup
        cache_key = f"tier_features:{tier_id}"
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                logger.info("[TIER_RESOLVE] Source: RedisCache | Tier: %d", tier_id)
                data = json.loads(cached_data)
                data = self._normalize_feature_payload(data)
                return TierFeatures(**data)
        except (ConnectionError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("[TIER_CACHE_ERROR] Tier: %d | Error: %s", tier_id, exc)

        # 3. Backend API Fallback
        resolved_features = await self._fetch_from_backend(tier_id)
        if resolved_features:
            # Cache the successful result
            try:
                await self.redis.setex(
                    cache_key,
                    settings.tier_features_cache_ttl_seconds,
                    json.dumps(resolved_features.__dict__),
                )
            except ConnectionError as exc:
                logger.warning(
                    "[TIER_CACHE_WRITE_ERROR] Tier: %d | Error: %s", tier_id, exc
                )
            return resolved_features

        # 4. Final Hardcoded Fallback
        logger.warning("[TIER_RESOLVE] Source: StaticFallback | Tier: %d", tier_id)
        return get_static_policy(tier_id)

    async def _fetch_from_backend(self, tier_id: int) -> TierFeatures | None:
        """Fetch tier definition from the master database via Backend API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {}
                if settings.ml_data_transfer_token:
                    headers["Authorization"] = (
                        f"Bearer {settings.ml_data_transfer_token}"
                    )

                response = await client.get(
                    f"{self.backend_url}/{tier_id}/features", headers=headers
                )
                if response.status_code == 200:
                    logger.info("[TIER_RESOLVE] Source: BackendAPI | Tier: %d", tier_id)
                    data = response.json()
                    # Expecting data format matching TierFeatures constructor
                    data = self._normalize_feature_payload(data)
                    return TierFeatures(**data)

                logger.error(
                    "[TIER_FETCH_FAILED] Tier: %d | Status: %s | Body: %s",
                    tier_id,
                    response.status_code,
                    response.text[:100],
                )
        except (httpx.RequestError, TypeError, ValueError) as exc:
            logger.error(
                "[TIER_BACKEND_UNREACHABLE] Tier: %d | Error: %s", tier_id, exc
            )

        return None

    @staticmethod
    def _normalize_feature_payload(data: dict[str, Any]) -> dict[str, Any]:
        """Backfill missing flags from older tier payload contracts."""
        normalized = dict(data)
        normalized.setdefault("direct_llm_only", False)
        return normalized


# Global resolver instance
resolver = TierFeatureResolver()
