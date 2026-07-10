import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scraping import ScrapingJobHistory, ScrapingURL

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parse ISO datetime safely."""
    if not dt_str:
        return None

    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except ValueError as exc:
        logger.warning("Could not parse datetime %s: %s", dt_str, exc)
        return None


def update_existing_job(existing_job: ScrapingJobHistory, job_data: dict) -> None:
    """Update existing scraping job history record."""
    existing_job.status = job_data.get("status")
    existing_job.error = job_data.get("error")

    datetime_fields = [
        "queued_at",
        "started_at",
        "in_progress_at",
        "completed_at",
    ]

    for field in datetime_fields:
        value = job_data.get(field)
        if value:
            setattr(existing_job, field, parse_iso_datetime(value))


async def sync_active_jobs(db: Session) -> None:
    """
    Fetch live status of active jobs from ML Scraper API
    and sync them to ScrapingJobHistory table.
    """
    ml_api_url = settings.ML_API_URL.rstrip("/")
    endpoint = f"{ml_api_url}/api/v1/scraper/active_jobs"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            data = response.json()

        if not data.get("success"):
            logger.error("Failed to fetch active jobs: %s", data)
            return

        jobs = data.get("jobs", [])

        for job_data in jobs:
            website_id = job_data.get("website_id")
            job_id = job_data.get("job_id")

            if not website_id or not job_id:
                continue

            valid_url = (
                db.query(ScrapingURL).filter(ScrapingURL.id == website_id).first()
            )

            if not valid_url:
                logger.debug(
                    "Skipping sync for job %s: website_id %s not found in local db.",
                    job_id,
                    website_id,
                )
                continue

            existing_job = (
                db.query(ScrapingJobHistory)
                .filter(ScrapingJobHistory.job_id == job_id)
                .first()
            )

            if existing_job:
                update_existing_job(existing_job, job_data)
                continue

            new_job = ScrapingJobHistory(
                run_id=job_data.get("run_id"),
                job_id=job_id,
                website_id=website_id,
                name=job_data.get("name"),
                status=job_data.get("status"),
                queued_at=parse_iso_datetime(job_data.get("queued_at")),
                started_at=parse_iso_datetime(job_data.get("started_at")),
                in_progress_at=parse_iso_datetime(job_data.get("in_progress_at")),
                completed_at=parse_iso_datetime(job_data.get("completed_at")),
                error=job_data.get("error"),
            )

            db.add(new_job)

        db.commit()

    except httpx.HTTPError as exc:
        logger.warning("Could not reach ML Scraper API: %s", exc)

    except (ValueError, TypeError) as exc:
        db.rollback()
        logger.error("Error syncing scraping jobs: %s", exc)


async def trigger_scraper_job(doc_id: str, s3_url: str) -> bool:
    """
    Trigger the ML Scraper to process a PDF file from S3.
    """
    ml_api_url = settings.ML_API_URL.rstrip("/")
    endpoint = f"{ml_api_url}/api/v1/scraper/scrape"

    payload = {"doc_id": doc_id, "s3_url": s3_url, "store_in_vector_db": True}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"Triggering ML Scraper: {endpoint}")
            print(f"Payload: {payload}")
            response = await client.post(endpoint, json=payload)
            print(f"ML Scraper Response Status: {response.status_code}")
            print(f"ML Scraper Response Body: {response.text}")
            response.raise_for_status()
            logger.info("Successfully triggered ML scraper for doc_id: %s", doc_id)
            return True
    except httpx.HTTPError as exc:
        logger.error("Failed to trigger ML scraper for doc_id %s: %s", doc_id, exc)
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error triggering ML scraper for doc_id %s: %s", doc_id, exc
        )
        return False


async def delete_document_from_ml(document_id: str) -> bool:
    """
    Delete a document from the ML vector store.
    """
    ml_api_url = settings.ML_API_URL.rstrip("/")
    endpoint = f"{ml_api_url}/api/v1/scraper/rag/document"
    params = {"document_id": document_id}

    print(f"Deleting document from ML: {endpoint} with id {document_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(endpoint, params=params)
            print(f"ML Delete Response Status: {response.status_code}")
            print(f"ML Delete Response Body: {response.text}")
            response.raise_for_status()
            logger.info(
                "Successfully deleted document from ML for document_id: %s", document_id
            )
            return True
    except httpx.HTTPError as exc:
        logger.error(
            "Failed to delete document from ML for document_id %s: %s", document_id, exc
        )
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error deleting document from ML for document_id %s: %s",
            document_id,
            exc,
        )
        return False
