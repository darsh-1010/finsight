"""
Utility script to safely wipe and recreate the DocumentChunks collection.
Use this to fix persistent "strategy mismatch" panics by creating a fresh collection
with the new canonical schema.
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.scripts.scraper_ingestion import ingest_to_weaviate
from src.services.weaviate.client import WeaviateClientManager
from src.services.weaviate.collections import CollectionManager
from src.utils.logger import get_logger

try:
    from . import path_bootstrap
except ImportError:
    import path_bootstrap

logger = get_logger(__name__)
OUTPUTS_DIR = Path(path_bootstrap.PROJECT_ROOT_STR) / "outputs"


def _get_output_files() -> list[Path]:
    """Return saved scraper output files that can be re-ingested."""
    if not OUTPUTS_DIR.exists():
        return []
    return sorted(OUTPUTS_DIR.glob("*_articles.json"))


def _get_scraper_name(output_file: Path) -> str:
    """Derive scraper name from the output filename."""
    return output_file.name.replace("_articles.json", "")


async def refresh_weaviate_schema():
    """Wipe, recreate, and repopulate the main Weaviate collection."""
    try:
        logger.info(
            "[SCHEMA_REFRESH_START] Initiating a full reset and refresh of the AI knowledge base. "
            "This ensures the system is using the most up-to-date document structure."
        )

        # Wait for Weaviate to be ready
        WeaviateClientManager.ensure_ready(timeout=30)

        # Force recreate collection
        CollectionManager.ensure_collection(force_recreate=True)

        output_files = _get_output_files()
        if not output_files:
            logger.warning(
                "No scraper JSON files found in %s. Schema refresh completed without re-ingestion.",
                OUTPUTS_DIR,
            )
        else:
            total_chunks = 0
            start_time = datetime.now(UTC)
            logger.info(
                "Re-ingesting %d scraper output files from %s",
                len(output_files),
                OUTPUTS_DIR,
            )

            for output_file in output_files:
                scraper_name = _get_scraper_name(output_file)
                logger.info("Re-ingesting %s", output_file)
                total_chunks += await ingest_to_weaviate(
                    str(output_file), scraper_name, start_time
                )

            logger.info("Re-ingestion complete. Total chunks stored: %d", total_chunks)

        logger.info(
            "[SCHEMA_REFRESH_SUCCESS] The AI knowledge base has been successfully refreshed with the canonical schema. "
            f"A total of {total_chunks if 'total_chunks' in locals() else 0} fragments have been re-indexed. "
            "The system is now fully synchronized and ready for queries."
        )

    except (ConnectionError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to refresh Weaviate schema: {e}")
        sys.exit(1)
    finally:
        WeaviateClientManager.close()


if __name__ == "__main__":
    asyncio.run(refresh_weaviate_schema())
