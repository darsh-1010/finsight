"""Standalone Scraper Scheduler.

This module reads the scraper configurations and runs the enabled scrapers
on a schedule based on their `lookback_days` configuration:
- 1 day: Daily
- 7 days: Weekly
- 30 days: Monthly

It includes a `--test-mode` to verify scraping output to a temporary JSON
and log Weaviate ingestion attempts without altering the primary workflow.

Run this script from the project root as a module:
    python -m src.scripts.scraper_scheduler --test-mode
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Callable, Optional, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from src.api.routes.scraper_mapping import (WEBSITE_INTERVAL_MAP,
                                            load_website_id_map)
from src.scripts.scraper_helpers import (cleanup_memory, collect_scraper_jobs,
                                         get_max_workers, is_scraper_due,
                                         load_config, parse_run_time)
from src.scripts.scraper_ingestion import (_resolve_output_file,
                                           ingest_to_weaviate_with_report)
from src.scripts.scraper_job_queue import ScraperJobQueue
from src.scripts.scraper_registry import SCRAPER_MAP
from src.scripts.scraper_snapshot import (IngestionReport, StoredArticleRecord,
                                          publish_scheduler_snapshot)
from src.scripts.scraper_watchdog import (ScraperWatchdog,
                                          check_and_cleanup_ghosts)
from src.services.scrapper.resilience import build_retry_decision
from src.utils.config_updater import update_scraper_intervals
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis

load_dotenv()

logger = get_logger(__name__)

# Default per-scraper runtime limit (30 minutes)
DEFAULT_MAX_RUNTIME_SECONDS = 1800

# Stealthed Firefox scrapers that need serial execution to prevent shared memory exhaustion
CAMOUFOX_SCRAPERS = frozenset(
    {"morgan_stanley", "schwab", "bofa_private_bank", "goldmansachs"}
)


class WatchdogManager:
    """Holder for the global ScraperWatchdog instance to avoid global statement."""

    _watchdog: Optional[ScraperWatchdog] = None

    @classmethod
    def get(cls, global_config: Optional[dict] = None) -> ScraperWatchdog:
        """Lazy-load and return the global ScraperWatchdog instance."""
        if cls._watchdog is None:
            cfg = global_config or load_config() or {}
            settings = cfg.get("settings", {})
            cls._watchdog = ScraperWatchdog(
                redis_client=get_redis(),
                zero_streak_threshold=int(
                    settings.get("watchdog_zero_streak_threshold", 3)
                ),
                cooldown_hours=int(settings.get("watchdog_cooldown_hours", 24)),
            )
        return cls._watchdog


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions for Scraper execution
# ──────────────────────────────────────────────────────────────────────────────


async def _call_function_scraper(
    scraper_fn: Callable, lookback_days: int, max_articles: int, output_file: str
) -> None:
    """Invoke a function-based (standalone async main) scraper.

    Args:
        scraper_fn: The async main function to call.
        lookback_days: Number of days to look back.
        max_articles: Maximum articles to fetch.
        output_file: Destination JSON file path.
    """
    await scraper_fn(
        lookback_days=lookback_days,
        max_articles=max_articles,
        output_file=output_file,
    )


async def _ingest_and_log_results(
    output_file: str,
    name: str,
    start_time: datetime,
    action_tag: str,
    job_queue: ScraperJobQueue,
) -> IngestionReport:
    """Helper to count articles, ingest to Weaviate, and update job status.

    Extracting this from run_scraper to keep local variable count compliant (max 15).
    """
    article_count = 0
    ingestion_report = IngestionReport()

    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f_handle:
                data = json.load(f_handle)
                article_count = len(data.get("articles", []))
        except (json.JSONDecodeError, OSError):
            pass

    if article_count > 0:
        ingestion_report = await ingest_to_weaviate_with_report(
            output_file, name, start_time
        )

    logger.info(
        f"[{action_tag}] {name} completed successfully. Articles: {article_count}, "
        f"Chunks: {ingestion_report.chunks_stored}"
    )
    job_queue.mark_completed(
        name,
        articles=article_count,
        chunks=ingestion_report.chunks_stored,
    )
    return ingestion_report


async def _execute_scraper_loop(
    scraper_entry: Union[type, Callable],
    name: str,
    run_params: dict,
    internal_queue: ScraperJobQueue,
    watchdog: ScraperWatchdog,
) -> list[StoredArticleRecord]:
    """Execute the scraper retry/repair loop."""
    attempt = 1
    while attempt <= run_params["max_repair_attempts"]:
        try:
            internal_queue.mark_in_progress(name)
            start_time = datetime.now(timezone.utc)
            if not isinstance(scraper_entry, type):
                coro = _call_function_scraper(
                    scraper_entry,
                    run_params["lookback_days"],
                    run_params["max_articles"],
                    run_params["output_file"],
                )
            else:
                scraper = scraper_entry(
                    lookback_days=run_params["lookback_days"],
                    max_articles=run_params["max_articles"],
                    output_file=run_params["output_file"],
                )
                # Instance based scrapers adopt a public scrape_async() method
                coro = scraper.scrape_async()

            # Enforce hard wall-clock timeout to prevent ghost/zombie hangs
            try:
                await asyncio.wait_for(coro, timeout=run_params["max_runtime"])
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(
                    f"Scraper '{name}' exceeded max runtime of {run_params['max_runtime']}s"
                ) from None

            ingestion_report = await _ingest_and_log_results(
                run_params["output_file"],
                name,
                start_time,
                run_params["action_tag"],
                internal_queue,
            )
            stored_articles = ingestion_report.stored_articles
            if len(stored_articles) > 0:
                watchdog.record_successful_run(name)
            else:
                logger.warning(
                    f"[{run_params['action_tag']}_ZERO_ARTICLES] Scraper '{name}' completed but returned 0 articles."
                )
                watchdog.record_zero_run(name)
            return stored_articles

        except asyncio.CancelledError:
            logger.error(
                f"[{run_params['action_tag']}_CANCELLED] {name} was cancelled (browser teardown timeout)."
            )
            internal_queue.mark_failed(
                name, "Cancelled — Playwright browser teardown timeout"
            )
            watchdog.record_zero_run(name)
            raise
        except Exception as exc:
            decision = build_retry_decision(
                exc, attempt, run_params["max_repair_attempts"]
            )
            logger.error(
                f"[{run_params['action_tag']}_ERROR] {name} failed"
                f" | attempt={attempt}/{run_params['max_repair_attempts']}"
                f" | category={decision.category}"
                f" | retry={decision.should_retry}"
                f" | reason={decision.reason}"
                f" | error={exc}",
                exc_info=True,
            )
            if not decision.should_retry:
                internal_queue.mark_failed(name, f"[{decision.category}] {exc}")
                watchdog.record_zero_run(name)
                return []
            await asyncio.sleep(decision.delay_seconds)
            attempt += 1
    return []


async def run_scraper(
    name: str,
    scraper_entry: Union[type, Callable],
    config: dict,
    *,
    is_test: bool = False,
    action_tag: str = "SCRAPER_RUN",
    job_queue: Optional[ScraperJobQueue] = None,
) -> list[StoredArticleRecord]:
    """Execute a single scraper and optionally ingest its data into Weaviate.

    Args:
        name: Name of the scraper (must match a SCRAPER_MAP key).
        scraper_entry: The scraper class or async main function from SCRAPER_MAP.
        config: Configuration dictionary for this specific scraper.
        is_test: If True, saves to a temporary file and fetches only 1 article.
        action_tag: Tag for log messages (e.g., 'TEST_MODE', 'CRON_MODE').
        job_queue: ScraperJobQueue instance for writing Redis status updates.
    """
    logger.info(f"[{action_tag}] Starting scraper: {name} (Test Mode: {is_test})")

    # Watchdog circuit breaker check
    watchdog = WatchdogManager.get()
    if watchdog.is_circuit_open(name):
        logger.warning(
            f"[{action_tag}_SKIP] Scraper '{name}' skipped because its circuit breaker is OPEN."
        )
        return []

    # If job_queue is none, we are likely in a scheduled background run.
    # We initialize a new one to ensure the status is visible to the API.
    internal_queue = job_queue
    if not internal_queue:
        internal_queue = ScraperJobQueue(
            redis_client=get_redis(), run_id=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        internal_queue.enqueue_job(name)

    lookback_days = config.get("lookback_days", 1)
    interval_days = config.get("interval_days", lookback_days)

    # Interval check: Skip if not due (unless in test mode)
    if not is_test:
        if not is_scraper_due(name, interval_days, datetime.now(), internal_queue):
            logger.info(
                f"[{action_tag}_SKIP] {name} is not due yet (interval: {interval_days}d)."
            )
            return []

    internal_queue.mark_started(name)

    # Enforce lookback >= interval to ensure no data gaps
    if lookback_days < interval_days:
        logger.warning(
            f"[{action_tag}] {name}: lookback_days ({lookback_days}) < interval_days ({interval_days}). "
            f"Increasing lookback to {interval_days} to avoid data gaps."
        )
        lookback_days = interval_days

    max_articles = 1 if is_test else config.get("max_articles", 50)
    output_file = _resolve_output_file(name, is_test, action_tag, config)

    max_runtime = config.get("max_runtime_seconds", DEFAULT_MAX_RUNTIME_SECONDS)
    max_repair_attempts = int(config.get("max_repair_attempts", 3))

    run_params = {
        "lookback_days": lookback_days,
        "max_articles": max_articles,
        "output_file": output_file,
        "max_runtime": max_runtime,
        "max_repair_attempts": max_repair_attempts,
        "action_tag": action_tag,
    }

    return await _execute_scraper_loop(
        scraper_entry, name, run_params, internal_queue, watchdog
    )


# ──────────────────────────────────────────────────────────────────────────────
# Scheduler setup
# ──────────────────────────────────────────────────────────────────────────────


def _build_trigger(hour: int, minute: int, tz_name: str) -> CronTrigger:
    """Build a daily CronTrigger for the given time."""
    return CronTrigger(hour=hour, minute=minute, timezone=tz_name)


def schedule_jobs(scheduler: AsyncIOScheduler, config: dict, settings: dict) -> None:
    """Parse configuration and schedule jobs based on lookback_days.

    Args:
        scheduler: The APScheduler instance to register jobs on.
        config: Scraper configuration dictionary (keyed by scraper name).
        settings: Global scraper settings (e.g., run_time).
    """
    run_time_str = settings.get("run_time", "00:00")
    hour, minute = parse_run_time(run_time_str)
    # Read timezone from env — default to UTC if not set so behaviour is explicit
    tz_name = os.environ.get("SCRAPER_TIMEZONE", "UTC")
    logger.info(
        f"[SCHEDULE_INIT] Global daily run time set to {hour:02d}:{minute:02d} ({tz_name})"
    )

    trigger = _build_trigger(hour, minute, tz_name)
    scheduler.add_job(
        run_scheduled_batch,
        trigger=trigger,
        args=[{"scrapers": config, "settings": settings}],
        name="scheduled_scraper_batch",
    )
    logger.info(
        f"[SCHEDULE_ADDED] Daily scraper batch scheduled for {hour:02d}:{minute:02d}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# One-shot run helpers (--test-mode / --cron)
# ──────────────────────────────────────────────────────────────────────────────


async def run_startup_check(config: dict) -> None:
    """On startup, check if any enabled scrapers are overdue and run them immediately.

    This ensures that if the system was down during the scheduled fixed-time window,
    the data is still fetched as soon as the system recovers.

    Args:
        config: Full configuration dictionary containing 'scrapers' and 'settings'.
    """
    logger.info("[STARTUP_CHECK] Verifying if any scrapers are overdue...")
    scrapers_cfg = config.get("scrapers", {})
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    job_queue = ScraperJobQueue(redis_client=get_redis(), run_id=run_id)

    due_jobs = []
    for name, cfg in scrapers_cfg.items():
        if not cfg.get("enabled", False):
            continue

        lookback = cfg.get("lookback_days", 1)
        interval = cfg.get("interval_days", lookback)
        if is_scraper_due(name, interval, now, job_queue):
            logger.info(
                f"[STARTUP_CHECK] {name} is overdue (interval={interval}d). Running now."
            )
            due_jobs.append((name, cfg))

    if due_jobs:
        max_workers = get_max_workers(config)
        await run_scrapers_async(
            jobs=due_jobs,
            max_workers=max_workers,
            action_tag="STARTUP_CATCHUP",
            is_test=False,
            job_queue=job_queue,
        )
    else:
        logger.info("[STARTUP_CHECK] All scrapers are up to date.")


async def run_scrapers_async(
    jobs: list,
    max_workers: int,
    action_tag: str,
    is_test: bool,
    job_queue: ScraperJobQueue,
) -> None:
    """Run multiple scrapers concurrently in the same event loop with a concurrency limit.

    This architecture ensures that only one event loop exists per process, allowing
    libraries like Playwright and Crawlee to perform background cleanup reliably.

    Args:
        jobs: List of (name, cfg) tuples.
        max_workers: Maximum number of simultaneous scrapers.
        action_tag: Log tag for this run (e.g. 'CRON_MODE', 'TEST_MODE').
        is_test: Whether to run in test mode (fetches 1 article).
        job_queue: ScraperJobQueue instance for Redis reporting.
    """
    semaphore = asyncio.Semaphore(max_workers)
    camoufox_semaphore = asyncio.Semaphore(1)
    stored_articles: list[StoredArticleRecord] = []

    # Enqueue all jobs upfront so status is immediately visible in Redis
    for name, _ in jobs:
        job_queue.enqueue_job(name)

    logger.info(
        f"[{action_tag}] Dispatching {len(jobs)} scraper(s) "
        f"using single-loop async with max_concurrency={max_workers}"
    )

    async def _sem_run(name: str, cfg: dict):
        async with semaphore:
            try:
                # Camoufox serialisation: only one Firefox/Camoufox scraper launches at a time
                # to prevent Docker shared memory (/dev/shm) exhaustion.
                if name in CAMOUFOX_SCRAPERS:
                    async with camoufox_semaphore:
                        scraper_articles = await run_scraper(
                            name,
                            SCRAPER_MAP[name],
                            cfg,
                            is_test=is_test,
                            action_tag=action_tag,
                            job_queue=job_queue,
                        )
                else:
                    scraper_articles = await run_scraper(
                        name,
                        SCRAPER_MAP[name],
                        cfg,
                        is_test=is_test,
                        action_tag=action_tag,
                        job_queue=job_queue,
                    )
                stored_articles.extend(scraper_articles)
            except asyncio.CancelledError:
                # run_scraper already logged and marked failed; absorb here so that
                # other scrapers in the gather pool are not cancelled.
                logger.error(f"[{action_tag}_CANCELLED] {name} task was cancelled.")
            except Exception as exc:
                logger.error(
                    f"[{action_tag}_ASYNC_ERROR] {name} failed: {exc}", exc_info=True
                )
                job_queue.mark_failed(name, str(exc))
            finally:
                # Always cleanup memory after a scraper finishes
                cleanup_memory(action_tag)

    # return_exceptions=True prevents one scraper's CancelledError from propagating
    # to asyncio.gather() and silently cancelling all remaining sibling scrapers.
    await asyncio.gather(
        *[_sem_run(name, cfg) for name, cfg in jobs], return_exceptions=True
    )

    _log_execution_summary(jobs, action_tag, job_queue, stored_articles)


def _log_execution_summary(
    jobs: list,
    action_tag: str,
    job_queue: ScraperJobQueue,
    stored_articles: list,
) -> None:
    """Log the post-run execution summary and publish the snapshot."""
    final_jobs = job_queue.get_all_jobs()
    success_count = sum(1 for j in final_jobs if j.status == "COMPLETED")
    fail_count = sum(1 for j in final_jobs if j.status == "FAILED")
    total_articles = sum(j.articles_scraped for j in final_jobs)
    total_chunks = sum(j.chunks_indexed for j in final_jobs)

    logger.info("=" * 60)
    logger.info(f"[{action_tag}] EXECUTION SUMMARY")
    logger.info("-" * 60)
    logger.info(f"Total Websites Attempted : {len(jobs)}")
    logger.info(f"Successfully Completed   : {success_count}")
    logger.info(f"Failed / Issues          : {fail_count}")
    logger.info(f"Total New Articles Found : {total_articles}")
    logger.info(f"Total Chunks in Weaviate : {total_chunks}")
    for job in final_jobs:
        logger.info(
            f"[{action_tag}_SITE_SUMMARY] website={job.name} | status={job.status} | "
            f"articles={job.articles_scraped} | chunks={job.chunks_indexed}"
        )
    logger.info("-" * 60)

    if fail_count > 0:
        failed_names = [j.name for j in final_jobs if j.status == "FAILED"]
        logger.error(f"Failed Scrapers: {', '.join(failed_names)}")

    snapshot_run_id = (
        final_jobs[0].run_id if final_jobs else datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    publish_scheduler_snapshot(snapshot_run_id, stored_articles)
    logger.info("=" * 60)


async def run_scheduled_batch(config: dict) -> None:
    """Run one scheduler-owned batch and publish a combined latest snapshot."""
    action_tag = "SCHEDULED_RUN"
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    job_queue = ScraperJobQueue(redis_client=get_redis(), run_id=run_id)
    jobs = collect_scraper_jobs(
        scrapers_cfg=config.get("scrapers", {}),
        is_cron=True,
        action_tag=action_tag,
        now=now,
        redis_client=get_redis(),
    )
    if not jobs:
        publish_scheduler_snapshot(run_id, [])
        logger.info(f"[{action_tag}] No due scrapers found for this batch.")
        return

    await run_scrapers_async(
        jobs=jobs,
        max_workers=get_max_workers(config),
        action_tag=action_tag,
        is_test=False,
        job_queue=job_queue,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    """Main entry point for the scheduler script."""
    parser = argparse.ArgumentParser(description="Standalone Scraper Scheduler")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run all enabled scrapers immediately for 1 article and save to /tmp",
    )
    parser.add_argument(
        "--cron",
        action="store_true",
        help="Run only due scrapers once and exit",
    )
    args = parser.parse_args()

    config = load_config()
    if not config:
        logger.error(
            "[CRITICAL] Cannot start scheduler without configuration. Exiting."
        )
        sys.exit(1)

    # Clean up any 'dirty' state from previous crashes before starting.
    # This prevents ghost jobs from lingering in the /active_jobs list.
    job_queue = ScraperJobQueue(redis_client=get_redis(), run_id="startup_cleanup")
    job_queue.cleanup_stale_jobs()

    # Active ghost-job cleanup: scans started/in-progress jobs older than max_runtime
    # and resets them to FAILED, logging a clear timestamp check.
    check_and_cleanup_ghosts(
        job_queue=job_queue,
        max_runtime_seconds=DEFAULT_MAX_RUNTIME_SECONDS,
    )

    # 1. Fetch latest mapping and intervals from backend API
    load_website_id_map()

    # 2. Synchronize these intervals to the configuration file on disk
    update_scraper_intervals(WEBSITE_INTERVAL_MAP)

    # 3. Reload config from the updated file
    new_config = load_config()
    if new_config:
        config = new_config
    else:
        logger.warning(
            "[STARTUP] Failed to reload configuration after sync. Continuing with initial config."
        )

    if args.test_mode or args.cron:
        action_tag = "TEST_MODE" if args.test_mode else "CRON_MODE"
        logger.info(f"[{action_tag}] Starting sequence...")

        # run_id uniquely identifies this batch so all job keys are isolated
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_queue = ScraperJobQueue(redis_client=get_redis(), run_id=run_id)

        jobs = collect_scraper_jobs(
            scrapers_cfg=config.get("scrapers", {}),
            is_cron=args.cron,
            action_tag=action_tag,
            now=datetime.now(),
            redis_client=get_redis(),
        )

        if jobs:
            max_workers = get_max_workers(config)
            await run_scrapers_async(
                jobs=jobs,
                max_workers=max_workers,
                action_tag=action_tag,
                is_test=args.test_mode,
                job_queue=job_queue,
            )
            logger.info(
                f"[{action_tag}] Final job statuses: {job_queue.get_all_statuses()}"
            )
        else:
            logger.info(f"[{action_tag}] No tasks to run.")

        logger.info(f"[{action_tag}] Sequence complete.")
        return

    # Normal Scheduler Mode
    logger.info("[STARTUP] Initializing Scraper Scheduler...")

    # Immediate Startup Catch-up Check
    await run_startup_check(config)

    scheduler = AsyncIOScheduler()
    schedule_jobs(scheduler, config.get("scrapers", {}), config.get("settings", {}))
    scheduler.start()
    logger.info("[STARTUP] Scheduler started. Press Ctrl+C to exit.")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("[SHUTDOWN] Exiting scheduler...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
