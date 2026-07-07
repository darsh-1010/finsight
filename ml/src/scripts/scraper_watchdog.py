"""Scraper Watchdog — circuit breaker and ghost-job cleanup.

This module provides two independent reliability mechanisms:

1.  **ScraperWatchdog** — tracks consecutive zero-article runs per scraper
    in Redis and trips a circuit breaker after a configurable threshold.
    When open, the scraper is skipped for a cooldown window, then retried
    once (HALF_OPEN state) to probe recovery.

2.  **check_and_cleanup_ghosts()** — called at scheduler startup to find
    any jobs stuck in ``STARTED`` or ``IN_PROGRESS`` state beyond their
    max_runtime and reset them to ``FAILED``.  This fixes the ghost-job
    Redis state that occurs when a browser process is killed by the OS
    before the scheduler's exception handler runs.

Redis key schema (all with 48-hour TTL):
    watchdog:{name}:zero_streak    — int, consecutive zero-article runs
    watchdog:{name}:circuit_opened — ISO timestamp when circuit was tripped
    watchdog:{name}:circuit_state  — "CLOSED" | "OPEN" | "HALF_OPEN"
"""

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Optional

from redis.exceptions import RedisError

from src.scripts.scraper_job_queue import JobStatus, ScraperJobQueue

logger = logging.getLogger(__name__)

# Redis key templates
_KEY_ZERO_STREAK = "watchdog:{name}:zero_streak"
_KEY_CIRCUIT_OPENED = "watchdog:{name}:circuit_opened"
_KEY_CIRCUIT_STATE = "watchdog:{name}:circuit_state"

# Circuit states
_STATE_CLOSED = "CLOSED"
_STATE_OPEN = "OPEN"
_STATE_HALF_OPEN = "HALF_OPEN"

# TTL for all watchdog keys — 48 hours
_WATCHDOG_KEY_TTL = 172800

# Default configuration values
_DEFAULT_ZERO_STREAK_THRESHOLD = 3
_DEFAULT_COOLDOWN_HOURS = 24
_DEFAULT_GHOST_BUFFER_SECONDS = 300


class ScraperWatchdog:
    """Tracks per-scraper health and enforces circuit-breaker behaviour.

    Reads and writes to Redis to persist state across scheduler restarts.
    All Redis operations are non-blocking and wrapped in try/except to
    ensure watchdog failures never break the main scraper pipeline.

    Attributes:
        zero_streak_threshold: Consecutive zero-article runs before circuit opens.
        cooldown_hours: Hours to skip the scraper after circuit trips.
        redis_client: Raw Redis connection.
    """

    def __init__(
        self,
        redis_client: object,
        zero_streak_threshold: int = _DEFAULT_ZERO_STREAK_THRESHOLD,
        cooldown_hours: int = _DEFAULT_COOLDOWN_HOURS,
    ) -> None:
        """Initialise the watchdog with Redis and circuit-breaker parameters.

        Args:
            redis_client: An active Redis client instance.
            zero_streak_threshold: Trips circuit after this many consecutive zero runs.
            cooldown_hours: Hours the circuit stays OPEN before moving to HALF_OPEN.
        """
        self._redis = redis_client
        self.zero_streak_threshold = zero_streak_threshold
        self.cooldown_hours = cooldown_hours

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def is_circuit_open(self, name: str) -> bool:
        """Return True if this scraper's circuit is open (should be skipped).

        Transitions OPEN → HALF_OPEN automatically when the cooldown has elapsed.

        Args:
            name: Scraper identifier.

        Returns:
            True if scraper should be skipped this run.
        """
        state = self._get_circuit_state(name)
        if state == _STATE_CLOSED:
            return False
        if state == _STATE_HALF_OPEN:
            # Allow a single probe run
            return False
        # OPEN — check if cooldown has elapsed
        opened_at = self._get_circuit_opened_at(name)
        if not opened_at:
            self._set_circuit_state(name, _STATE_CLOSED)
            return False
        cooldown_end = opened_at + timedelta(hours=self.cooldown_hours)
        now = datetime.now(UTC)
        if now >= cooldown_end:
            self._set_circuit_state(name, _STATE_HALF_OPEN)
            logger.info(
                "[WATCHDOG_HALF_OPEN] Scraper: %s | Cooldown elapsed — probing recovery.",
                name,
            )
            return False
        remaining = (cooldown_end - now).total_seconds() / 3600
        logger.warning(
            "[WATCHDOG_OPEN] Scraper: %s | Circuit open — skipping. "
            "Cooldown remaining: %.1fh",
            name,
            remaining,
        )
        return True

    def record_zero_run(self, name: str) -> None:
        """Record a zero-article run and trip the circuit if threshold is reached.

        Args:
            name: Scraper identifier.
        """
        streak = self._increment_zero_streak(name)
        logger.warning(
            "[WATCHDOG_ZERO_RUN] Scraper: %s | Zero-article streak: %d/%d",
            name,
            streak,
            self.zero_streak_threshold,
        )
        if streak >= self.zero_streak_threshold:
            state = self._get_circuit_state(name)
            if state != _STATE_OPEN:
                self._trip_circuit(name)

    def record_successful_run(self, name: str) -> None:
        """Reset the zero-article streak and close the circuit on a good run.

        Args:
            name: Scraper identifier.
        """
        self._reset_zero_streak(name)
        self._set_circuit_state(name, _STATE_CLOSED)
        logger.info(
            "[WATCHDOG_RESET] Scraper: %s | Circuit closed — streak reset.", name
        )

    # ──────────────────────────────────────────────
    # Private Redis helpers
    # ──────────────────────────────────────────────

    def _get_circuit_state(self, name: str) -> str:
        try:
            raw = self._redis.get(_KEY_CIRCUIT_STATE.format(name=name))
            return raw.decode() if raw else _STATE_CLOSED
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            return _STATE_CLOSED

    def _set_circuit_state(self, name: str, state: str) -> None:
        try:
            self._redis.set(
                _KEY_CIRCUIT_STATE.format(name=name), state, ex=_WATCHDOG_KEY_TTL
            )
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            pass

    def _get_circuit_opened_at(self, name: str) -> datetime | None:
        try:
            raw = self._redis.get(_KEY_CIRCUIT_OPENED.format(name=name))
            if not raw:
                return None
            return datetime.fromisoformat(raw.decode())
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            return None

    def _trip_circuit(self, name: str) -> None:
        now_iso = datetime.now(UTC).isoformat()
        try:
            self._redis.set(
                _KEY_CIRCUIT_OPENED.format(name=name), now_iso, ex=_WATCHDOG_KEY_TTL
            )
            self._set_circuit_state(name, _STATE_OPEN)
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            pass
        logger.error(
            "[WATCHDOG_CIRCUIT_OPEN] Scraper: %s | Circuit tripped after %d "
            "consecutive zero-article runs. Skipping for %dh.",
            name,
            self.zero_streak_threshold,
            self.cooldown_hours,
        )

    def _increment_zero_streak(self, name: str) -> int:
        key = _KEY_ZERO_STREAK.format(name=name)
        try:
            streak = self._redis.incr(key)
            self._redis.expire(key, _WATCHDOG_KEY_TTL)
            return int(streak)
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            return 0

    def _reset_zero_streak(self, name: str) -> None:
        try:
            self._redis.set(_KEY_ZERO_STREAK.format(name=name), 0, ex=_WATCHDOG_KEY_TTL)
        except (RedisError, AttributeError, TypeError, ValueError):  # noqa
            pass


def check_and_cleanup_ghosts(
    job_queue: ScraperJobQueue,
    max_runtime_seconds: int,
    ghost_buffer_seconds: int = _DEFAULT_GHOST_BUFFER_SECONDS,
) -> None:
    """Reset stale IN_PROGRESS / STARTED jobs to FAILED at scheduler startup.

    A ghost job occurs when the browser process is killed by the OS (e.g.
    OOM) before the scheduler's exception handler can call ``mark_failed()``.
    This leaves the Redis job state permanently as IN_PROGRESS, causing the
    dashboard to show the scraper as "running" indefinitely.

    Called once at startup before ``run_startup_check()`` to clean the slate.

    Args:
        job_queue: ScraperJobQueue instance for Redis access.
        max_runtime_seconds: Per-scraper runtime ceiling from config.
        ghost_buffer_seconds: Extra grace period on top of max_runtime.
    """
    stale_threshold = max_runtime_seconds + ghost_buffer_seconds
    all_jobs = job_queue.get_all_jobs()

    for job in all_jobs:
        if job.status not in (JobStatus.STARTED, JobStatus.IN_PROGRESS):
            continue

        if not job.started_at:
            continue

        started = job.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)

        age_seconds = (datetime.now(UTC) - started).total_seconds()
        if age_seconds > stale_threshold:
            job_queue.mark_failed(
                job.scraper_name,
                f"ghost_cleanup: job was {age_seconds:.0f}s old (limit {stale_threshold}s)",
            )
            logger.warning(
                "[GHOST_CLEANUP] Scraper: %s | Job age: %.0fs | "
                "Threshold: %ds | Marked as FAILED.",
                job.scraper_name,
                age_seconds,
                stale_threshold,
            )
