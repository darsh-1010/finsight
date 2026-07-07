import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

logger = logging.getLogger("cron")

# A job is an async callable that takes no arguments
Job = Callable[[], Awaitable[None]]


class CronService:
    def __init__(self, interval_seconds: int | None = None):
        # default interval comes from env or settings, fallback to 60s
        self.interval = interval_seconds or int(
            os.getenv("CRON_INTERVAL_SECONDS", "60")
        )
        self._jobs: list[Job] = []
        self._runner: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    def register(self, job: Job) -> None:
        """Register an async job (callable with no args)."""
        self._jobs.append(job)

    async def _run_once(self) -> None:
        for job in list(self._jobs):
            try:
                await job()
            except Exception:
                logger.exception("Cron job raised an exception")

    async def _loop(self) -> None:
        self._stop_event = asyncio.Event()
        while not self._stop_event.is_set():
            await self._run_once()
            try:
                # wait for stop event with timeout = interval
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
            except TimeoutError:
                # timeout means continue to next iteration
                continue

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        logger.info("Starting CronService (interval=%ss)", self.interval)
        self._runner = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if not self._runner:
            return
        logger.info("Stopping CronService")
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
        try:
            await self._runner
        except asyncio.CancelledError:
            pass


# Export a single shared instance other modules can import and register jobs on
cron_service = CronService()


# helper to register jobs from other modules
def register_job(job: Job) -> None:
    cron_service.register(job)


# Example job - replace with real work (DB cleanup, scraping kickoffs, etc.)
async def _example_job() -> None:
    logger.info("[cron] running example job")


# Register example job (safe noop in many contexts)
register_job(_example_job)
