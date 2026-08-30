"""Scraper Ingestion and Output Helpers.

This module handles the ingestion of scraped data into Weaviate and
manages file path resolution for scraper outputs.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from src.scripts.scraper_snapshot import (
    IngestionReport,
    StoredArticleRecord,
    notify_backend_deleted_documents,
)
from src.services.rag.rag_service import RAGService
from src.services.scrapper.date_filter import parse_date

logger = logging.getLogger(__name__)


def _resolve_output_file(
    name: str, is_test: bool, action_tag: str, config: dict
) -> str:
    """Determine the output file path for a scraper run.

    Temporary outputs (test and cron modes) are written to .agents/temp/
    in the project root so they remain accessible and organised.
    Permanent outputs (scheduled mode) use the path from scraper_config.yaml.

    Args:
        name: Scraper name.
        is_test: Whether this is a test run.
        action_tag: Mode tag for this run (e.g. 'TEST_MODE', 'CRON_MODE').
        config: Scraper config dict.

    Returns:
        Absolute path string for the output JSON file.
    """
    temp_dir = Path(__file__).parent.parent.parent / ".agents" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if is_test:
        return str(temp_dir / f"test_output_{name}.json")
    if action_tag == "CRON_MODE":
        return str(temp_dir / f"cron_{name}.json")

    output_path = config.get("output_file", f"outputs/{name}_articles.json")
    path = Path(output_path)

    # Ensure absolute path based on project root if relative
    if not path.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        path = project_root / path

    return str(path)


def _collect_source_counts(
    articles: list[dict], fallback_source: str
) -> dict[str, int]:
    """Build a per-source article count map for ingestion summary logs."""
    source_counts: dict[str, int] = {}
    for article in articles:
        source_name = str(article.get("source") or fallback_source)
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
    return source_counts


async def ingest_to_weaviate(
    output_file: str, scraper_name: str, start_time: datetime
) -> int:
    """Backward-compatible wrapper that returns only the stored chunk count."""
    report = await ingest_to_weaviate_with_report(
        output_file=output_file,
        scraper_name=scraper_name,
        start_time=start_time,
    )
    return report.chunks_stored


async def _accumulate_ingestion_results(
    rag: RAGService, articles: list[dict]
) -> tuple[int, int, list[StoredArticleRecord]]:
    """Ingest all articles and accumulate chunk/article counts.

    Extracted to keep ingest_to_weaviate_with_report within the local-variable limit.

    Args:
        rag: Initialised RAGService instance.
        articles: List of article dicts to ingest.

    Returns:
        Tuple of (total_chunks, indexed_articles, stored_articles).
    """
    total_chunks = 0
    indexed_articles = 0
    stored_articles: list[StoredArticleRecord] = []

    for article in articles:
        chunk_count, stored_article = await _ingest_article(rag, article)
        total_chunks += chunk_count
        if chunk_count > 0 and stored_article:
            indexed_articles += 1
            stored_articles.append(stored_article)

    return total_chunks, indexed_articles, stored_articles


async def ingest_to_weaviate_with_report(
    output_file: str, scraper_name: str, start_time: datetime
) -> IngestionReport:
    """Read a JSON file and store its articles in Weaviate using RAGService.

    Args:
        output_file: Source JSON file.
        scraper_name: Scraper ID (source).
        start_time: Start time of the run (for clearing old data).

    Returns:
        Structured ingestion report for the scraper output file.
    """
    msg = (
        f"[WEAVIATE_INGEST] Now processing scraper output from '{output_file}'. "
        f"This updates our database with the freshest scraped articles."
    )
    logger.info(msg)
    try:
        if not os.path.exists(output_file):
            return IngestionReport()

        with open(output_file, encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        articles = data.get("articles", [])
        source_counts = _collect_source_counts(articles, scraper_name)

        rag = RAGService()

        if not articles:
            logger.warning("[WEAVIATE_INGEST] No articles found to ingest.")
            await _cleanup_old_scraper_data(rag, scraper_name, start_time)
            return IngestionReport()

        (
            total_chunks,
            indexed_articles,
            stored_articles,
        ) = await _accumulate_ingestion_results(rag, articles)

        logger.info(
            "[WEAVIATE_SUCCESS] Successfully stored %d total chunks.", total_chunks
        )
        logger.info(
            "[WEAVIATE_INGEST_SUMMARY] scraper=%s | articles_found=%d | articles_indexed=%d | sources=%s",
            scraper_name,
            len(articles),
            indexed_articles,
            source_counts,
        )

        await _cleanup_old_scraper_data(rag, scraper_name, start_time)

        return IngestionReport(
            chunks_stored=total_chunks,
            indexed_articles=indexed_articles,
            stored_articles=stored_articles,
        )

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        err_msg = f"[WEAVIATE_ERROR] Failed to process {output_file}: {exc}"
        logger.error(err_msg, exc_info=True)
        return IngestionReport()


async def _cleanup_old_scraper_data(
    rag: RAGService, scraper_name: str, start_time: datetime
) -> None:
    """Delete stale chunks for a scraper after the latest scrape output is processed."""
    if not hasattr(rag, "vector_service") or not hasattr(
        rag.vector_service, "delete_old_scraper_data"
    ):
        return

    logger.info(
        "[WEAVIATE_CLEANUP] Routine cleanup: Deleting stale chunks for '%s' that were created before %s. "
        "This prevents the existence of duplicate or outdated information in the AI system.",
        scraper_name,
        start_time,
    )
    _, deleted_document_ids = await rag.vector_service.delete_old_scraper_data(
        scraper_name, start_time
    )
    await notify_backend_deleted_documents(deleted_document_ids)


def _build_stored_article_record(
    article: dict, iso_published_date: str | None
) -> StoredArticleRecord:
    """Build the snapshot record for one article after successful storage."""
    scraped_at = str(
        article.get("scraped_at") or datetime.now(UTC).isoformat()
    )
    return StoredArticleRecord(
        source=str(article.get("source", "unknown")),
        url=str(article.get("url", "")),
        title=str(article.get("title", "Untitled")),
        summary=str(article.get("summary", "")),
        published_date=iso_published_date,
        scraped_at=scraped_at,
        scraper_version=str(article.get("scraper_version", "unknown")),
    )


async def _ingest_article(
    rag: RAGService, article: dict
) -> tuple[int, StoredArticleRecord | None]:
    """Ingest a single article into Weaviate and return its storage result.

    Args:
        rag: Initialized RAGService instance.
        article: Article dict with title, source, url, content, published_date.

    Returns:
        Tuple of stored chunk count and the snapshot record when storage succeeds.
    """
    try:
        raw_date = article.get("published_date")
        iso_date = None
        if raw_date:
            dt = parse_date(str(raw_date))
            if dt:
                iso_date = dt.isoformat()

        metadata = {
            "title": article.get("title", "Untitled"),
            "source": article.get("source", "unknown"),
            # Tag as scraped-web article so WeaviateService.search_similar_by_source_type
            # can filter by source_type="url" at query time
            "source_type": "url",
            "published_date": iso_date,
        }
        chunks = await rag.store_document(
            url=article.get("url", ""),
            content=article.get("content", ""),
            metadata=metadata,
        )
        msg = f"[WEAVIATE_INGEST] Stored {chunks} chunks for {article.get('url')}"
        logger.debug(msg)
        if chunks <= 0:
            return 0, None
        stored_article = _build_stored_article_record(article, iso_date)
        return chunks, stored_article
    except RuntimeError as exc:
        err_msg = (
            f"[WEAVIATE_ERROR] Failed to store article {article.get('url')}: {exc}"
        )
        logger.error(err_msg)
    return 0, None
