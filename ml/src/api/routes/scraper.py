"""Scraper API route handlers."""

import uuid
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


from src.api.routes.scraper_mapping import (SCRAPER_KEY_TO_ID, WEBSITE_ID_MAP,
                                            load_website_id_map)
from src.scripts.scraper_job_queue import ScraperJobQueue
from src.services.rag import RAGService
from src.services.scrapper.scrapper_service import ScrapperService
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/scraper", tags=["Scraper & RAG"])


@lru_cache()
def get_scrapper_service() -> ScrapperService:
    """Get or create scrapper service instance."""
    return ScrapperService()


@lru_cache()
def get_rag_service() -> RAGService:
    """Get or create RAG service instance."""
    return RAGService()



# ============================================================================
# Pydantic Schemas
# ============================================================================


class ScrapeRequest(BaseModel):
    """Request to scrape a single PDF via S3 URL."""

    s3_url: str = Field(..., description="S3 URL (s3://bucket/key.pdf) or HTTPS S3 URL")
    doc_id: str = Field(..., description="Document ID for tracking/RAG")
    store_in_vector_db: bool = Field(
        default=False, description="Whether to store scraped content in vector database"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "s3_url": "s3://finsight-staging/reports/doc1.pdf",
                "doc_id": "DOC-12345",
                "store_in_vector_db": True,
            }
        }
    )


class ScrapeResult(BaseModel):
    """Result of a single scrape operation."""

    url: str
    status: str
    content_length: int = 0
    chunks_stored: int = 0
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ScrapeResponse(BaseModel):
    """Response from scraping operation."""

    results: list[ScrapeResult]
    total: int
    successful: int
    failed: int


class StoreDocumentRequest(BaseModel):
    """Request to store document in vector database."""

    url: str
    content: str
    metadata: Optional[dict] = None


class RetrieveContextRequest(BaseModel):
    """Request to retrieve context from RAG."""

    query: str
    limit: Optional[int] = None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/scrape", response_model=ScrapeResponse, summary="Scrape PDF document from S3"
)
async def scrape_pdfs(request: ScrapeRequest):
    """
    Scrape content from PDF via S3 URL.

    - **s3_url**: S3 URL or HTTPS S3 URL
    - **doc_id**: Document ID for tracking and RAG metadata
    - **store_in_vector_db**: If true, automatically store in vector database

    Returns scraped content with metadata.
    """
    try:
        logger.info(f"Scraping document from S3 (doc_id={request.doc_id})")
        scrapper = get_scrapper_service()

        # Scrape the S3 source (using batch service with one item for stability)
        batch_result = await scrapper.scrape_batch([request.s3_url])

        results = []
        for scrape_result in batch_result["results"]:
            # Attach document_id to metadata
            metadata = scrape_result.metadata or {}
            metadata["document_id"] = request.doc_id

            # Phase 4: Provenance Enrichment
            metadata["source_name"] = metadata.get("title") or "FinSight Research"
            try:
                domain = urlparse(scrape_result.url).netloc
                metadata["source_domain"] = domain or "institutional-research"
            except (ValueError, AttributeError):
                metadata["source_domain"] = "institutional-research"

            result_dict = {
                "url": scrape_result.url,
                "status": scrape_result.status,
                "content_length": (
                    len(scrape_result.content) if scrape_result.content else 0
                ),
                "chunks_stored": 0,
                "error": scrape_result.error,
                "metadata": metadata,
            }

            # Optionally store in vector database
            if request.store_in_vector_db and scrape_result.status == "success":
                try:
                    rag = get_rag_service()
                    # Pass the metadata (containing doc_id) to RAG
                    chunks = await rag.store_document(
                        url=scrape_result.url,
                        content=scrape_result.content,
                        metadata=metadata,
                    )
                    result_dict["chunks_stored"] = chunks
                    logger.info(f"Stored {chunks} chunks for {scrape_result.url}")

                except (ValueError, AttributeError, RuntimeError) as e:
                    logger.error(f"Failed to store in vector DB: {e}")
                    result_dict["error"] = f"Scrape OK, but storage failed: {str(e)}"
                    result_dict["status"] = "partial_success"

            results.append(ScrapeResult(**result_dict))

        return ScrapeResponse(
            results=results,
            total=1,
            successful=batch_result["successful"],
            failed=batch_result["failed"],
        )

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping operation failed: {str(e)}",
        ) from e


@router.post("/rag/store", summary="Store document in vector database")
async def store_document(request: StoreDocumentRequest):
    """
    Store document content in vector database for RAG.

    - **url**: Document URL (used for deduplication)
    - **content**: Document text content
    - **metadata**: Optional metadata (title, author, etc.)

    Returns number of chunks stored.
    """
    try:
        rag = get_rag_service()
        chunks = await rag.store_document(
            url=request.url, content=request.content, metadata=request.metadata
        )

        return {
            "success": True,
            "url": request.url,
            "chunks_stored": chunks,
            "message": f"Successfully stored {chunks} chunks",
        }

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Document storage failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store document: {str(e)}",
        ) from e


# ── Website ID ↔ Scraper Name Mapping ──────────────────────────────────────────


@router.post("/rag/retrieve", summary="Retrieve context from RAG")
async def retrieve_context(request: RetrieveContextRequest):
    """
    Retrieve relevant document chunks for a query.

    - **query**: Search query
    - **limit**: Maximum number of documents to return (optional)

    Returns relevant document chunks with metadata and scores.
    """
    try:
        rag = get_rag_service()
        results = await rag.retrieve_context(query=request.query, limit=request.limit)

        return {
            "success": True,
            "query": request.query,
            "results": results,
            "count": len(results),
        }

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Context retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve context: {str(e)}",
        ) from e


@router.delete("/rag/document", summary="Delete document from vector database")
async def delete_document(document_id: str):
    """
    Delete document by ID from vector database.

    - **document_id**: Document ID to delete

    Returns confirmation of deletion.
    """
    try:
        rag = get_rag_service()
        success = await rag.delete_document_by_id(document_id)

        if success:
            return {"success": True, "message": f"Document deleted: {document_id}"}

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Document deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        ) from e


@router.get("/rag/stats", summary="Get RAG statistics")
async def get_rag_stats():
    """Get statistics about stored documents in vector database."""
    try:
        rag = get_rag_service()
        stats = await rag.get_document_stats()

        return {"success": True, "stats": stats}

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}",
        ) from e


@router.get("/job_status/{website_id}", summary="Get job status for a specific website")
async def get_job_status_by_website(website_id: int):
    """
    Get the most recent scraper job status for a specific website by its ID.
    Returns the most recent job record for that website from Redis.
    """
    # Ensure the map is initialised (guards against cold-start edge cases).
    if not WEBSITE_ID_MAP:
        load_website_id_map()

    scraper_name = WEBSITE_ID_MAP.get(website_id)
    if not scraper_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Website ID {website_id} not recognised. Valid IDs: {sorted(WEBSITE_ID_MAP.keys())}",
        )

    try:
        redis_client = get_redis()
        job_queue = ScraperJobQueue(redis_client=redis_client, run_id="lookup")
        job = job_queue.get_job_for_scraper(scraper_name)

        if not job:
            return {
                "success": True,
                "website_id": website_id,
                "scraper_name": scraper_name,
                "job": None,
                "message": f"No job record found for '{scraper_name}'. Has the scheduler run yet?",
            }

        return {
            "success": True,
            "website_id": website_id,
            "scraper_name": scraper_name,
            "job": {
                "job_id": f"{job.run_id}:{job.name}",
                "run_id": job.run_id,
                "name": job.name,
                "status": job.status,
                "queued_at": job.queued_at,
                "started_at": job.started_at,
                "in_progress_at": job.in_progress_at,
                "completed_at": job.completed_at,
                "error": job.error,
                "articles_scraped": job.articles_scraped,
                "chunks_indexed": job.chunks_indexed,
            },
        }

    except (ValueError, AttributeError, RuntimeError) as e:
        logger.error(
            "Failed to get job status for website %d: %s", website_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}",
        ) from e


@router.get("/active_jobs", summary="Get all active and recent jobs from Redis")
async def get_active_jobs():
    """
    Return every scraper job currently stored in Redis across all runs.

    No input required. Covers all jobs regardless of their status —
    including QUEUED, IN_PROGRESS, COMPLETED, and FAILED — as long as
    they are within the 24-hour Redis TTL window.

    Returns jobs sorted by most recent run first.
    """
    try:
        redis_client = get_redis()
        job_queue = ScraperJobQueue(redis_client=redis_client, run_id="lookup")
        jobs = job_queue.get_all_recent_jobs()

        # Ensure the map is populated before we try to reverse-lookup IDs.
        if not WEBSITE_ID_MAP:
            load_website_id_map()

        return {
            "success": True,
            "total_jobs": len(jobs),
            "jobs": [
                {
                    "job_id": f"{job.run_id}:{job.name}",
                    "run_id": job.run_id,
                    "name": job.name,
                    # Attach the numeric website_id so callers don't need to
                    # maintain their own reverse-lookup table.
                    "website_id": SCRAPER_KEY_TO_ID.get(job.name),
                    "status": job.status,
                    "queued_at": job.queued_at,
                    "started_at": job.started_at,
                    "in_progress_at": job.in_progress_at,
                    "completed_at": job.completed_at,
                    "error": job.error,
                    "articles_scraped": job.articles_scraped,
                    "chunks_indexed": job.chunks_indexed,
                }
                for job in jobs
            ],
        }

    except (ValueError, AttributeError, RuntimeError) as exc:
        logger.error("Failed to get active jobs: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active jobs: {str(exc)}",
        ) from exc
