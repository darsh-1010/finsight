"""Helpers for publishing the latest scheduler-wide article snapshot."""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import asdict, dataclass, field

import requests

from src.api.routes.scraper_mapping import SCRAPER_KEY_TO_ID, load_website_id_map
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class StoredArticleRecord:
    """Article metadata captured only after successful Weaviate persistence."""

    source: str
    url: str
    title: str
    summary: str
    published_date: str | None
    scraped_at: str
    scraper_version: str


@dataclass(slots=True)
class IngestionReport:
    """Result of ingesting one scraper output file into Weaviate."""

    chunks_stored: int = 0
    indexed_articles: int = 0
    stored_articles: list[StoredArticleRecord] = field(default_factory=list)


@dataclass(slots=True)
class SchedulerSnapshotItem:
    """Scheduler-wide snapshot item for one successfully indexed article."""

    scraping_url_id: int
    document_id: str
    source: str
    url: str
    title: str
    summary: str
    published_date: str | None
    scraped_at: str
    scraper_version: str


def _build_snapshot_payload(
    stored_articles: list[StoredArticleRecord],
) -> list[dict[str, object]]:
    """Build the latest-run snapshot payload."""
    if not SCRAPER_KEY_TO_ID:
        load_website_id_map()

    return [
        asdict(
            SchedulerSnapshotItem(
                scraping_url_id=SCRAPER_KEY_TO_ID.get(article.source, 0),
                document_id=str(uuid.uuid5(uuid.NAMESPACE_URL, article.url)),
                source=article.source,
                url=article.url,
                title=article.title,
                summary=article.summary,
                published_date=article.published_date,
                scraped_at=article.scraped_at,
                scraper_version=article.scraper_version,
            )
        )
        for article in stored_articles
    ]


async def notify_backend_deleted_documents(document_ids: list[str]) -> None:
    """Notify the backend that documents have been deleted from the vector database.

    Sends a DELETE request to the ml-data-transfer endpoint so the backend
    can remove the corresponding records from its own database.
    This runs asynchronously to prevent blocking the scraper event loop.

    Args:
        document_ids: List of unique document UUIDs deleted from Weaviate.
    """
    if not document_ids:
        return

    token = os.environ.get("ML_DATA_TRANSFER_TOKEN", "")
    if not token:
        logger.error("[DELETE_NOTIFY] ML_DATA_TRANSFER_TOKEN missing from env.")
        return

    base_url = os.environ.get(
        "ML_DATA_TRANSFER_BASE_URL", "http://localhost:8001"
    ).rstrip("/")
    api_url = f"{base_url}/api/v1/ml-data-transfer/scraping-content"
    headers = {
        "accept": "application/json",
        "x-ml-token": token,
        "Content-Type": "application/json",
    }

    try:
        # Wrap blocking requests call in to_thread to keep the async loop free
        response = await asyncio.to_thread(
            requests.delete,
            api_url,
            json={"document_ids": document_ids},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        logger.info(
            "[DELETE_NOTIFY] System synchronization complete: "
            "Successfully notified the backend about %d deleted documents. "
            "This ensures consistency between the vector database and the main dashboard.",
            len(document_ids),
        )
    except requests.RequestException as exc:
        logger.error(f"[DELETE_NOTIFY] Backend notification failed: {exc}")


def publish_scheduler_snapshot(
    run_id: str,
    stored_articles: list[StoredArticleRecord],
) -> str:
    """Send the scheduler snapshot to the backend API payload."""
    if not stored_articles:
        logger.info(
            f"[SCHEDULER_SNAPSHOT] run_id={run_id} | items=0 | No articles to send."
        )
        return ""

    payload = _build_snapshot_payload(stored_articles)

    token = os.environ.get("ML_DATA_TRANSFER_TOKEN", "")
    if not token:
        logger.error("[SCHEDULER_SNAPSHOT] ML_DATA_TRANSFER_TOKEN missing from env.")
        return ""

    headers = {
        "accept": "application/json",
        "x-ml-token": token,
        "Content-Type": "application/json",
    }

    # Base URL should be defined in .env (e.g., http://host.docker.internal:8001 or https://api.chatfinsight.ai)
    base_url = os.environ.get(
        "ML_DATA_TRANSFER_BASE_URL", "http://localhost:8001"
    ).rstrip("/")
    api_url = f"{base_url}/api/v1/ml-data-transfer/scraping-content"

    try:
        # Timeout set to 30s to account for network jitter and latency
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info(
            f"[SCHEDULER_SNAPSHOT] run_id={run_id} | items={len(stored_articles)} | "
            f"Successfully sent payload. Status: {response.status_code}"
        )
        return "API_SUCCESS"
    except requests.RequestException as exc:
        logger.error(f"[SCHEDULER_SNAPSHOT] API failure. run_id={run_id} | error={exc}")
        return "API_FAILURE"
