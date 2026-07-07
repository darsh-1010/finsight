"""
Backend cron runner
===================

Usage
-----
# Run the scheduler forever (normal production mode)
python -m app.cron

# Run the token-refill tick once and exit
python -m app.cron --once

# Immediately trigger the DAILY insights sync and exit (for testing)
python -m app.cron --test-daily

# Immediately trigger the WEEKLY insights sync and exit (for testing)
python -m app.cron --test-weekly

# Immediately trigger BOTH syncs and exit (for testing)
python -m app.cron --test-daily --test-weekly
"""

import argparse
import asyncio
import logging
import signal

from app.core.database import SESSION_LOCAL
from app.services.cron_service import CronService
from app.services.insights_sync_service import sync_insights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def run_test_sync(mode: str) -> None:
    """Immediately execute a single insights sync and print a summary."""
    logger.info("=== TEST MODE: running %s insights sync now ===", mode.upper())
    db = SESSION_LOCAL()
    try:
        count = await sync_insights(db, mode=mode)
        db.commit()
        logger.info(
            "=== TEST COMPLETE: %s sync saved %d insight(s) to the database. ===",
            mode.upper(),
            count,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "=== TEST FAILED: %s insights sync raised an exception. ===", mode.upper()
        )
    finally:
        db.close()


async def main(run_once: bool, test_daily: bool, test_weekly: bool) -> None:
    # --- test modes: run immediately and exit ---
    if test_daily or test_weekly:
        tasks = []
        if test_daily:
            tasks.append(run_test_sync("daily"))
        if test_weekly:
            tasks.append(run_test_sync("weekly"))
        await asyncio.gather(*tasks)
        return

    # --- one-shot tick (token refill only) ---
    service = CronService()
    if run_once:
        await service.run_once()
        return

    # --- normal long-running mode ---
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await service.run_forever(stop_event)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run backend cron jobs.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run interval-based cron jobs (token refill) once and exit.",
    )
    parser.add_argument(
        "--test-daily",
        action="store_true",
        help="Immediately trigger the DAILY insights sync and exit (for testing).",
    )
    parser.add_argument(
        "--test-weekly",
        action="store_true",
        help="Immediately trigger the WEEKLY insights sync and exit (for testing).",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            run_once=args.once,
            test_daily=args.test_daily,
            test_weekly=args.test_weekly,
        )
    )
