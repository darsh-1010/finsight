"""Helper utilities for the scraper scheduler.

Includes environment-aware config loading, date/time parsing, job eligibility collection,
and gc memory cleanup.
"""

import gc
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import yaml

from src.scripts.scraper_job_queue import JobStatus, ScraperJobQueue
from src.scripts.scraper_registry import SCRAPER_MAP

logger = logging.getLogger(__name__)

# Configuration file path
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "scraper_config.yaml"


def parse_run_time(time_str: str) -> tuple[int, int]:
    """Parse a time string (e.g., '12:30 PM', '02:00 AM', '14:30') into (hour, minute).

    Args:
        time_str: The time string to parse.

    Returns:
        tuple: (hour, minute) in 24-hour format.
    """
    time_str = time_str.strip().upper()

    # Try AM/PM format first
    am_pm_match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2))
        period = am_pm_match.group(3)
        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0
        return hour, minute

    # Try 24-hour format
    h24_match = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if h24_match:
        hour = int(h24_match.group(1))
        minute = int(h24_match.group(2))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute

    logger.warning(
        "[CONFIG_WARNING] Invalid run_time format '%s'. Defaulting to 00:00.", time_str
    )
    return 0, 0


def cleanup_memory(action_tag: str) -> None:
    """Force garbage collection and log that the cleanup is occurring.

    This helps ensure that after heavy Playwright instances are closed,
    the Python process releases as much memory as possible to keep
    the container within its 6GB limit.
    """
    gc.collect()
    logger.info("[%s_CLEANUP] Garbage collection manually triggered.", action_tag)


def load_config() -> dict:
    """Load the scraper configuration from yaml file.

    Returns:
        dict: The loaded configuration dictionary.
    """
    try:
        with open(CONFIG_PATH, encoding="utf-8") as file_handle:
            content = file_handle.read()
            # Expand ${ENV_VAR:-default} syntax
            content = re.sub(
                r"\$\{([A-Za-z0-9_]+):-([^}]*)\}",
                lambda m: os.environ.get(m.group(1), m.group(2)),
                content,
            )
            # Expand ${ENV_VAR} syntax
            content = re.sub(
                r"\$\{([A-Za-z0-9_]+)\}",
                lambda m: os.environ.get(m.group(1), m.group(0)),
                content,
            )
            return yaml.safe_load(content) or {}
    except FileNotFoundError:
        logger.error("[CONFIG_ERROR] Config file not found at %s", CONFIG_PATH)
        return {}


def get_max_workers(config: dict) -> int:
    """Read the maximum number of parallel scraper workers from config.

    The value is sourced from the SCRAPER_MAX_WORKERS environment variable
    via scraper_config.yaml settings.max_workers. Defaults to 1 if not set.

    Args:
        config: The full loaded configuration dictionary.

    Returns:
        int: Maximum number of concurrent scrapers to run simultaneously.
    """
    raw = config.get("settings", {}).get("max_workers", 1)
    try:
        workers = int(raw)
        if workers < 1:
            logger.warning("[CONFIG_WARNING] max_workers < 1, defaulting to 1.")
            return 1
        return workers
    except (TypeError, ValueError):
        return 1


def is_scraper_due(
    name: str, interval: float, now: datetime, job_queue: ScraperJobQueue
) -> bool:
    """Determine whether a scraper is due to run based on its status and interval.

    Follows the requested logic: if it is already running, it is not due (prevents double runs).
    If it never finished successfully or the interval has passed, it is due.

    Args:
        name: Scraper identifier.
        interval: Frequency in days between runs (can be float).
        now: Current datetime.
        job_queue: Queue instance for Redis access.

    Returns:
        True if the scraper should run; False otherwise.
    """
    # 1. Concurrency protection: Check if its already RUNNING in ANY run_id.
    current_job = job_queue.get_job_for_scraper(name)
    if current_job and current_job.status in (JobStatus.STARTED, JobStatus.IN_PROGRESS):
        logger.info(
            "[DUE_CHECK] %s is currently %s. Skipping duplication.",
            name,
            current_job.status,
        )
        return False

    # 2. Success check
    last_success = job_queue.get_last_success_timestamp(name)
    if not last_success:
        logger.info(
            "[DUE_CHECK] %s has no record of previous success. Triggering first run.",
            name,
        )
        return True

    # 3. Time interval check
    # Ensure naive comparison
    if last_success.tzinfo is not None:
        last_success = last_success.replace(tzinfo=None)
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    diff = now - last_success
    days_passed = diff.total_seconds() / 86400
    due = days_passed >= interval
    logger.info(
        "[DUE_CHECK] %s last ran %.2f days ago (Interval: %sd). Due: %s",
        name,
        days_passed,
        interval,
        due,
    )
    return due


def collect_scraper_jobs(
    scrapers_cfg: dict,
    is_cron: bool,
    action_tag: str,
    now: datetime,
    redis_client: object,
) -> list:
    """Build the list of (name, cfg) pairs eligible to run for the current mode.

    Args:
        scrapers_cfg: Full scrapers section from config.
        is_cron: Whether running in --cron mode.
        action_tag: Log tag for this run.
        now: Current datetime for eligibility checks in cron mode.
        redis_client: Redis connection to use for the check.

    Returns:
        List of (name, cfg) tuples for scrapers that should run.
    """
    jobs = []
    # In cron mode, we need a queue instance to check last-run timing
    run_id = now.strftime("%Y%m%d_%H%M%S")
    tmp_queue = ScraperJobQueue(redis_client=redis_client, run_id=run_id)

    for name, cfg in scrapers_cfg.items():
        if not cfg.get("enabled", False):
            logger.info("[%s_SKIP] %s is disabled in config.", action_tag, name)
            continue

        if name not in SCRAPER_MAP:
            logger.warning(
                "[%s_WARNING] Scraper '%s' not found in SCRAPER_MAP.", action_tag, name
            )
            continue

        lookback = cfg.get("lookback_days", 1)
        interval = cfg.get("interval_days", lookback)

        if is_cron and not is_scraper_due(name, interval, now, tmp_queue):
            logger.info(
                "[%s_SKIP] %s is not due (interval=%sd)", action_tag, name, interval
            )
            continue

        jobs.append((name, cfg))

    return jobs
