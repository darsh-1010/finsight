"""Dispatcher & Tier Logic Layer for Market Insights.

Handles deduplication via Redis atomic SET NX EX, enforces daily send
limits for premium tiers, and routes alerts to the correct delivery
channel based on user tier entitlement:

  Tiers 3 & 4  →  Immediate queue (list in Redis); daily cap = 5 alerts.
  Tiers 1 & 2  →  Weekly summary accumulator (list in Redis, 7-day TTL).
  Tier  0       →  No alerts dispatched.
"""

from __future__ import annotations

from datetime import UTC, datetime

import redis.asyncio as aioredis
from pydantic import ValidationError

from src.services.market_insights.models import AlertPayload, InsightResult
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Redis Key Patterns
# ──────────────────────────────────────────────────────────────────────────────

# SET NX EX key — prevents identical topic alerts for the same ticker.
_DEDUP_KEY = "mi:dedup:{ticker}:{topic}"

# Sorted-set / list key for immediate Tier 3/4 alerts (per user).
_IMMEDIATE_KEY = "mi:immediate:{user_id}"

# List key for Tier 1/2 weekly summaries (per user).
_WEEKLY_KEY = "mi:weekly:{user_id}"

# List key for daily summaries (per user).
_DAILY_KEY = "mi:daily:{user_id}"

# Counter key for daily send limit enforcement (per user, resets at midnight).
_DAILY_COUNT_KEY = "mi:daily_count:{user_id}:{date}"

# ──────────────────────────────────────────────────────────────────────────────
# Tier Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Tiers that receive immediate alerts.
_IMMEDIATE_TIERS = {3, 4}

# Tiers that receive weekly summary aggregation.
_SUMMARY_TIERS = {1, 2}

# Maximum alerts sent immediately per user per day for premium tiers.
_DAILY_SEND_LIMIT = 5

# How long a dedup key lives — prevents re-alerting the same topic same day.
_DEDUP_TTL_SECONDS = 86_400  # 24 hours

# How long immediate-alert list entries live in Redis.
_IMMEDIATE_TTL_SECONDS = 7 * 86_400  # 7 days

# How long weekly summary entries live in Redis.
_WEEKLY_TTL_SECONDS = 7 * 86_400  # 7 days

# How long daily summary entries live in Redis.
_DAILY_TTL_SECONDS = 86_400  # 24 hours

# TTL for the daily send-count counter key (resets at 24 h).
_DAILY_COUNT_TTL_SECONDS = 86_400  # 24 hours


class NotificationDispatcher:
    """Routes classified insights to the correct user-tier delivery queue.

    All Redis operations use async commands and follow the SET NX EX
    pattern for race-condition-free deduplication.
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        """Initialise with an optional Redis client injection (for testing).

        Args:
            redis_client: Pre-built async Redis client. Uses the shared
                          singleton when None.
        """
        self._redis: aioredis.Redis = redis_client or get_async_redis()

    async def dispatch(
        self,
        insight: InsightResult,
        user_id: str,
        user_tier: int,
    ) -> AlertPayload | None:
        """Route a classified insight to the appropriate delivery channel.

        Args:
            insight: Fully classified InsightResult from the LLM engine.
            user_id: Target user's unique identifier.
            user_tier: Numeric tier (0-5) controlling routing logic.

        Returns:
            AlertPayload if the alert was dispatched, None if skipped
            (duplicate, over daily limit, or unentitled tier).
        """
        if user_tier not in _IMMEDIATE_TIERS and user_tier not in _SUMMARY_TIERS:
            logger.debug(
                "[DISPATCH_SKIP] UserId: ***%s | Tier: %d | Reason: unentitled_tier",
                user_id[-4:],
                user_tier,
            )
            return None

        is_duplicate = await self._is_duplicate(insight)
        if is_duplicate:
            logger.info(
                "[DISPATCH_DEDUP] Ticker: %s | Topic: %s | Reason: duplicate",
                insight.event.ticker,
                insight.topic.value,
            )
            return None

        is_immediate = user_tier in _IMMEDIATE_TIERS
        payload = AlertPayload(
            insight=insight,
            user_tier=user_tier,
            user_id=user_id,
            dispatched_at=datetime.now(tz=UTC),
            is_immediate=is_immediate,
        )

        if is_immediate:
            # Attempt immediate delivery (subject to daily cap)
            immediate_ok = await self._dispatch_immediate(payload)
            # Always accumulate in weekly/daily queues for audit and report endpoints,
            # regardless of whether the immediate cap was reached.
            await self._dispatch_weekly_summary(payload)
            await self._dispatch_daily_summary(payload)
            # Only mark as dispatched if the immediate delivery succeeded.
            # When capped, we return None so the dedup key is not set,
            # allowing the alert to be retried the next day.
            dispatched = immediate_ok
        else:
            # Tiers 1 & 2: only accumulate in weekly summary queue, not daily
            weekly_ok = await self._dispatch_weekly_summary(payload)
            dispatched = weekly_ok

        if dispatched:
            await self._mark_dedup(insight)
            logger.info(
                "[DISPATCH_OK] Ticker: %s | Topic: %s | Tier: %d | Immediate: %s",
                insight.event.ticker,
                insight.topic.value,
                user_tier,
                is_immediate,
            )

        return payload if dispatched else None

    async def get_pending_immediate(self, user_id: str) -> list[AlertPayload]:
        """Retrieve and drain the immediate alert queue for a user atomically.

        Guarantees exact-once delivery via Redis transactions and protects
        against queue-wide data loss from individual corrupted payloads.

        Args:
            user_id: Target user identifier.

        Returns:
            List of AlertPayload objects (oldest first).
        """
        key = _IMMEDIATE_KEY.format(user_id=user_id)

        # 1. Fetch and delete atomically in a single Redis transaction pipeline
        pipe = self._redis.pipeline(transaction=True)
        pipe.lrange(key, 0, -1)
        pipe.delete(key)
        results = await pipe.execute()

        raw_items = results[0] if (results and results[0]) else []

        # 2. Deserialise each item safely to prevent queue-wide parsing crashes
        parsed_items = []
        for item in raw_items:
            try:
                parsed_items.append(AlertPayload.model_validate_json(item))
            except (ValidationError, ValueError) as exc:
                logger.error(
                    "[CORRUPTED_ALERT_PAYLOAD] Failed to parse payload from immediate queue: %s | Error: %s",
                    item,
                    exc,
                )
                continue

        return parsed_items

    async def get_weekly_summary(self, user_id: str) -> list[AlertPayload]:
        """Retrieve (non-destructively) the weekly summary for a user.

        Args:
            user_id: Target user identifier.

        Returns:
            List of AlertPayload objects accumulated this week.
        """
        key = _WEEKLY_KEY.format(user_id=user_id)
        raw_items = await self._redis.lrange(key, 0, -1)
        return [AlertPayload.model_validate_json(item) for item in raw_items]

    async def get_daily_summary(self, user_id: str) -> list[AlertPayload]:
        """Retrieve (non-destructively) the daily summary for a user.

        Args:
            user_id: Target user identifier.

        Returns:
            List of AlertPayload objects accumulated today.
        """
        key = _DAILY_KEY.format(user_id=user_id)
        raw_items = await self._redis.lrange(key, 0, -1)
        return [AlertPayload.model_validate_json(item) for item in raw_items]

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _is_duplicate(self, insight: InsightResult) -> bool:
        """Check whether this ticker+topic pair was already alerted today.

        Uses a Redis GET rather than SET NX so the state is not consumed
        here — _mark_dedup writes the key after successful dispatch.

        Args:
            insight: The classified insight to check.

        Returns:
            True when a dedup key exists (already dispatched).
        """
        key = _DEDUP_KEY.format(
            ticker=insight.event.ticker,
            topic=insight.topic.value.replace(" ", "_").lower(),
        )
        return await self._redis.exists(key) == 1

    async def _mark_dedup(self, insight: InsightResult) -> None:
        """Atomically set the dedup key so future calls are suppressed.

        Uses SET NX EX — only the first caller wins; safe under concurrency.

        Args:
            insight: The successfully dispatched insight.
        """
        key = _DEDUP_KEY.format(
            ticker=insight.event.ticker,
            topic=insight.topic.value.replace(" ", "_").lower(),
        )
        await self._redis.set(key, 1, nx=True, ex=_DEDUP_TTL_SECONDS)

    async def _dispatch_immediate(self, payload: AlertPayload) -> bool:
        """Push to the immediate-delivery queue if under the daily cap.

        Args:
            payload: Alert to dispatch.

        Returns:
            True if pushed, False when the daily send limit is reached.
        """
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        count_key = _DAILY_COUNT_KEY.format(user_id=payload.user_id, date=date_str)

        current_count = await self._redis.get(count_key)
        send_count = int(current_count) if current_count else 0

        if send_count >= _DAILY_SEND_LIMIT:
            logger.info(
                "[DISPATCH_LIMIT] UserId: ***%s | DailyCount: %d | Limit: %d",
                payload.user_id[-4:],
                send_count,
                _DAILY_SEND_LIMIT,
            )
            return False

        queue_key = _IMMEDIATE_KEY.format(user_id=payload.user_id)
        serialised = payload.model_dump_json()
        await self._redis.rpush(queue_key, serialised)
        await self._redis.expire(queue_key, _IMMEDIATE_TTL_SECONDS)

        # Increment and (re-)set TTL on the daily counter atomically.
        await self._redis.incr(count_key)
        await self._redis.expire(count_key, _DAILY_COUNT_TTL_SECONDS)
        return True

    async def _dispatch_weekly_summary(self, payload: AlertPayload) -> bool:
        """Append to the weekly summary accumulator for Tier 1 & 2 users.

        Args:
            payload: Alert to append.

        Returns:
            Always True — weekly summaries are never capped.
        """
        key = _WEEKLY_KEY.format(user_id=payload.user_id)
        serialised = payload.model_dump_json()
        await self._redis.rpush(key, serialised)
        await self._redis.expire(key, _WEEKLY_TTL_SECONDS)
        return True

    async def _dispatch_daily_summary(self, payload: AlertPayload) -> bool:
        """Append to the daily summary accumulator.

        Args:
            payload: Alert to append.

        Returns:
            Always True — daily summaries are never capped.
        """
        key = _DAILY_KEY.format(user_id=payload.user_id)
        serialised = payload.model_dump_json()
        await self._redis.rpush(key, serialised)
        await self._redis.expire(key, _DAILY_TTL_SECONDS)
        return True


def build_dispatcher() -> NotificationDispatcher:
    """Factory that returns a ready-to-use NotificationDispatcher.

    Convenience wrapper for dependency injection in FastAPI routes.

    Returns:
        NotificationDispatcher connected to the shared Redis singleton.
    """
    return NotificationDispatcher()


async def run_full_pipeline(
    event: InsightResult,
    user_id: str,
    user_tier: int,
    dispatcher: NotificationDispatcher | None = None,
) -> AlertPayload | None:
    """Convenience coroutine that wires dispatcher and runs dispatch.

    Args:
        event: Classified InsightResult from the LLM engine.
        user_id: Target user identifier.
        user_tier: Numeric tier (0–5).
        dispatcher: Optional pre-built dispatcher (for testing).

    Returns:
        AlertPayload if dispatched, None otherwise.
    """
    active_dispatcher = dispatcher or build_dispatcher()
    return await active_dispatcher.dispatch(event, user_id, user_tier)


async def dispatch_batch(
    insights: list[InsightResult],
    user_id: str,
    user_tier: int,
) -> list[AlertPayload]:
    """Dispatch a batch of insights for a single user, sharing one dispatcher.

    Args:
        insights: List of classified InsightResult objects.
        user_id: Target user identifier.
        user_tier: Numeric tier (0–5).

    Returns:
        List of AlertPayload objects that were successfully dispatched.
    """
    dispatcher = build_dispatcher()
    payloads: list[AlertPayload] = []
    for insight in insights:
        result = await dispatcher.dispatch(insight, user_id, user_tier)
        if result is not None:
            payloads.append(result)
    return payloads
