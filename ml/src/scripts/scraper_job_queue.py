"""Redis-backed job queue for scraper status tracking.

Each scraper job transitions through defined statuses stored in Redis:

    QUEUED → STARTED → IN_PROGRESS → COMPLETED
                                   ↘ FAILED

Redis key format: scraper:job:{run_id}:{name}
TTL: 24 hours (86400 seconds) — enough to inspect after a daily cron run.

Run via scraper_scheduler.py; not intended to be executed standalone.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import redis

from src.utils.logger import get_logger

logger = get_logger(__name__)

# TTL: 24 hours — covers the full daily window without accumulating stale keys
JOB_KEY_TTL_SECONDS = 86400


class JobStatus(str, Enum):
    """Lifecycle statuses for a single scraper job."""

    QUEUED = "QUEUED"
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ScraperJob:
    """Snapshot of a single scraper job's state.

    Attributes:
        name: Scraper identifier (matches SCRAPER_MAP key).
        run_id: Unique identifier for the batch run (timestamp string).
        status: Current lifecycle status.
        queued_at: ISO timestamp when the job was queued.
        started_at: ISO timestamp when the thread started.
        in_progress_at: ISO timestamp when scraping began executing.
        completed_at: ISO timestamp when the job finished.
        error: Error message if status is FAILED, else None.
    """

    name: str
    run_id: str
    status: str = JobStatus.QUEUED
    queued_at: str | None = None
    started_at: str | None = None
    in_progress_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    articles_scraped: int = 0
    chunks_indexed: int = 0

    def to_json(self) -> str:
        """Serialize job state to a JSON string for Redis storage."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "ScraperJob":
        """Deserialize a ScraperJob from a Redis-stored JSON string.

        Args:
            raw: JSON string retrieved from Redis.

        Returns:
            Reconstructed ScraperJob dataclass instance.
        """
        return cls(**json.loads(raw))


# ──────────────────────────────────────────────────────────────────────────────
# Job Queue
# ──────────────────────────────────────────────────────────────────────────────


class ScraperJobQueue:
    """Manages scraper job lifecycle statuses in Redis.

    Each method updates the Redis key for a given scraper name and
    logs the state transition at INFO level.

    Args:
        redis_client: Connected redis.Redis instance.
        run_id: Unique identifier for this batch run (e.g. '20260317_155844').
    """

    def __init__(self, redis_client: redis.Redis, run_id: str) -> None:
        self._redis = redis_client
        self._run_id = run_id

    # ── Private helpers ────────────────────────────────────────────────────────

    def _make_key(self, name: str) -> str:
        """Build the Redis key for a scraper job (batch-specific)."""
        return f"scraper:job:{self._run_id}:{name}"

    def _make_last_success_key(self, name: str) -> str:
        """Build the permanent Redis key for a scraper's last successful run."""
        return f"scraper:last_success:{name}"

    def _read_job(self, name: str) -> ScraperJob | None:
        """Read and deserialize a job from Redis.

        Args:
            name: Scraper identifier.

        Returns:
            ScraperJob instance, or None if the key does not exist.
        """
        raw = self._redis.get(self._make_key(name))
        return ScraperJob.from_json(raw) if raw else None

    def _write_job(self, job: ScraperJob) -> None:
        """Persist a job to Redis with the configured TTL.

        Args:
            job: ScraperJob instance to persist.
        """
        self._redis.setex(self._make_key(job.name), JOB_KEY_TTL_SECONDS, job.to_json())

    # ── Status transitions ─────────────────────────────────────────────────────

    def enqueue_job(self, name: str) -> None:
        """Create a QUEUED job entry in Redis for the given scraper.

        Args:
            name: Scraper identifier.
        """
        job = ScraperJob(
            name=name,
            run_id=self._run_id,
            status=JobStatus.QUEUED,
            queued_at=datetime.now().isoformat(),
        )
        self._write_job(job)
        logger.info(f"[JOB_QUEUED] Scraper: {name} | Run: {self._run_id}")

    def mark_started(self, name: str) -> None:
        """Transition a job from QUEUED to STARTED.

        Called when the thread is assigned and begins initialising the scraper.

        Args:
            name: Scraper identifier.
        """
        job = self._read_job(name) or ScraperJob(name=name, run_id=self._run_id)
        job.status = JobStatus.STARTED
        job.started_at = datetime.now().isoformat()
        self._write_job(job)
        logger.info(f"[JOB_STARTED] Scraper: {name} | Website scraping started")

    def mark_in_progress(self, name: str) -> None:
        """Transition a job to IN_PROGRESS.

        Called immediately before the scraper begins its main execution.

        Args:
            name: Scraper identifier.
        """
        job = self._read_job(name) or ScraperJob(name=name, run_id=self._run_id)
        job.status = JobStatus.IN_PROGRESS
        job.in_progress_at = datetime.now().isoformat()
        self._write_job(job)
        logger.info(f"[JOB_IN_PROGRESS] Scraper: {name} | Scraping in progress")

    def mark_completed(self, name: str, articles: int = 0, chunks: int = 0) -> None:
        """Transition a job to COMPLETED and update the persistent last-success timestamp.

        Args:
            name: Scraper identifier.
            articles: Number of articles successfully scraped.
            chunks: Number of chunks successfully indexed in Weaviate.
        """
        job = self._read_job(name) or ScraperJob(name=name, run_id=self._run_id)
        job.status = JobStatus.COMPLETED
        now = datetime.now()
        job.completed_at = now.isoformat()
        job.articles_scraped = articles
        job.chunks_indexed = chunks
        self._write_job(job)

        # Update persistent timestamp (no TTL)
        self._redis.set(self._make_last_success_key(name), job.completed_at)

        logger.info(
            f"[JOB_COMPLETED] Scraper: {name} | "
            f"Articles: {articles} | Chunks: {chunks} | "
            "Scraping ended successfully"
        )

    def mark_failed(self, name: str, error: str) -> None:
        """Transition a job to FAILED and record the error message."""
        job = self._read_job(name) or ScraperJob(name=name, run_id=self._run_id)
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now().isoformat()
        job.error = error
        self._write_job(job)
        logger.error(f"[JOB_FAILED] Scraper: {name} | Error: {error}")

    def get_last_success_timestamp(self, name: str) -> datetime | None:
        """Retrieve the last successful completion time for a scraper from Redis.

        Args:
            name: Scraper identifier.

        Returns:
            Datetime object if found, else None.
        """
        raw = self._redis.get(self._make_last_success_key(name))
        if not raw:
            return None
        try:
            val = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return None

    # ── Inspection ─────────────────────────────────────────────────────────────

    def get_job_status(self, name: str) -> str | None:
        """Return the current status string for a scraper job.

        Args:
            name: Scraper identifier.

        Returns:
            Status string (e.g. 'IN_PROGRESS'), or None if not found.
        """
        job = self._read_job(name)
        return job.status if job else None

    def get_all_statuses(self) -> dict:
        """Return a dict of {name: status} for all jobs in this run.

        Uses Redis SCAN to avoid blocking on large keyspaces.

        Returns:
            Dict mapping scraper name to its current status string.
        """
        pattern = f"scraper:job:{self._run_id}:*"
        statuses = {}
        for key in self._redis.scan_iter(pattern):
            raw = self._redis.get(key)
            if raw:
                job = ScraperJob.from_json(raw)
                statuses[job.name] = job.status
        return statuses

    def get_all_recent_jobs(self) -> list[ScraperJob]:
        """Return the most recent ScraperJob for every scraper found in Redis.

        Optimized to use SCAN to find all available scrapers and their status.

        Returns:
            List of ScraperJob instances representing the latest run of each website.
        """
        pattern = "scraper:job:*"
        latest_jobs: dict[str, ScraperJob] = {}

        for key in self._redis.scan_iter(pattern):
            raw = self._redis.get(key)
            if raw:
                try:
                    job = ScraperJob.from_json(raw)
                    # Keep only the one with the latest run_id (lexicographical sort works for YYYYMMDD)
                    existing = latest_jobs.get(job.name)
                    if not existing or job.run_id > existing.run_id:
                        latest_jobs[job.name] = job
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    logger.error(f"Failed to decode job in get_all_recent_jobs: {exc}")

        return sorted(list(latest_jobs.values()), key=lambda x: x.name)

    def cleanup_stale_jobs(self) -> int:
        """Mark any lingering 'STARTED' or 'IN_PROGRESS' jobs from past runs as FAILED.

        Call this on startup to ensure ghost jobs from previous container instances
        don't stay 'stuck' in progress forever.
        """
        stale_count = 0
        all_latest = self.get_all_recent_jobs()

        for job in all_latest:
            if job.status in (JobStatus.STARTED, JobStatus.IN_PROGRESS):
                job.status = JobStatus.FAILED
                job.error = "Stale job: Interrupted by system restart or crash"
                job.completed_at = datetime.now().isoformat()

                # Write back into Redis under the original key
                key = f"scraper:job:{job.run_id}:{job.name}"
                self._redis.set(key, job.to_json())
                stale_count += 1
        if stale_count > 0:
            logger.info(
                f"[CLEANUP] Marked {stale_count} stale jobs as FAILED on startup."
            )
        return stale_count

    def get_latest_run_id(self) -> str | None:
        """Find the most recent run_id present in Redis.

        Returns:
            The latest run_id (string) or None if no jobs exist.
        """
        pattern = "scraper:job:*"
        run_ids = set()
        for key in self._redis.scan_iter(pattern):
            decoded_key = key.decode("utf-8") if isinstance(key, bytes) else key
            # Key format: scraper:job:{run_id}:{name}
            parts = decoded_key.split(":")
            if len(parts) >= 4:
                run_ids.add(parts[2])
        if not run_ids:
            return None
        return sorted(list(run_ids), reverse=True)[0]

    def get_all_jobs(self, run_id: str | None = None) -> list[ScraperJob]:
        """Return a list of all ScraperJob objects for a specific run_id.

        Args:
            run_id: The run ID to filter by. Defaults to the instance's _run_id.

        Returns:
            List of ScraperJob instances found in Redis.
        """
        target_run_id = run_id or self._run_id
        pattern = f"scraper:job:{target_run_id}:*"
        jobs = []
        for key in self._redis.scan_iter(pattern):
            raw = self._redis.get(key)
            if raw:
                try:
                    jobs.append(ScraperJob.from_json(raw))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to decode job data for key {key}: {e}")
        jobs.sort(key=lambda x: x.name)
        return jobs

    def get_job_for_scraper(self, scraper_name: str) -> ScraperJob | None:
        """Return the most recent ScraperJob for a given scraper name across all runs.

        Scans all Redis keys matching scraper:job:*:{scraper_name} then
        returns the one belonging to the latest run_id.

        Args:
            scraper_name: Scraper identifier (e.g. 'morgan_stanley').

        Returns:
            Most recent ScraperJob, or None if no job was found.
        """
        pattern = f"scraper:job:*:{scraper_name}"
        candidates: list[ScraperJob] = []
        for key in self._redis.scan_iter(pattern):
            raw = self._redis.get(key)
            if raw:
                try:
                    candidates.append(ScraperJob.from_json(raw))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to decode job data for key {key}: {e}")
        if not candidates:
            return None
        # Return the job from the most recent run (run_id is a sortable timestamp string)
        return sorted(candidates, key=lambda j: j.run_id, reverse=True)[0]
