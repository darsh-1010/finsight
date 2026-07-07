"""
OpenAI File Janitor Service.

This script lists all files uploaded to OpenAI and deletes those older than 24 hours.
Designed to be run as a daily Cron job or background task.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from src.llm.fallback_client import FallbackAsyncOpenAI

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Constants
# Delete files older than 24 hours to ensure session isolation and cost control
MAX_FILE_AGE_HOURS = 24


async def cleanup_openai_files() -> None:
    """List and delete old user_data files from OpenAI."""
    client = FallbackAsyncOpenAI(api_key=settings.openai_api_key)
    logger.info("[JANITOR_START] Scanning for orphaned OpenAI files...")

    try:
        # Fetch the list of files from OpenAI
        files_response = await client.files.list(purpose="user_data")
        files = files_response.data

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_FILE_AGE_HOURS)
        deleted_count = 0

        for file_info in files:
            # OpenAI created_at is a Unix timestamp
            created_at = datetime.fromtimestamp(file_info.created_at, tz=timezone.utc)

            if created_at < cutoff_time:
                logger.info(
                    "[JANITOR_CLEANUP] Deleting expired file: %s | Created: %s",
                    file_info.id,
                    created_at.isoformat(),
                )
                try:
                    await client.files.delete(file_info.id)
                    deleted_count += 1
                except (ValueError, TypeError, OSError, RuntimeError) as exc:
                    logger.warning(
                        "[JANITOR_ERROR] Failed to delete file %s: %s",
                        file_info.id,
                        exc,
                    )

        logger.info(
            "[JANITOR_COMPLETE] Cleanup finished. Deleted %d files.", deleted_count
        )

    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        logger.error("[JANITOR_CRITICAL] Failed to list OpenAI files: %s", exc)


if __name__ == "__main__":
    asyncio.run(cleanup_openai_files())
