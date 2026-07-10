"""Tests for scraper ingestion cleanup behavior."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.scripts.scraper_ingestion import ingest_to_weaviate


def test_cleanup_runs_when_output_has_no_articles(tmp_path):
    """Stale data cleanup should still run when the latest scrape returns zero articles."""
    output_file = tmp_path / "empty_articles.json"
    output_file.write_text('{"articles": []}', encoding="utf-8")
    start_time = datetime.now(timezone.utc)

    mock_rag = type(
        "MockRag",
        (),
        {
            "vector_service": type(
                "MockVectorService",
                (),
                {"delete_old_scraper_data": AsyncMock(return_value=(0, []))},
            )()
        },
    )()

    with patch("src.scripts.scraper_ingestion.RAGService", return_value=mock_rag):
        stored_chunks = asyncio.run(
            ingest_to_weaviate(str(output_file), "wealth_deutsche_bank", start_time)
        )

    assert stored_chunks == 0
    mock_rag.vector_service.delete_old_scraper_data.assert_awaited_once_with(
        "wealth_deutsche_bank",
        start_time,
    )
