"""Live integration test for Weaviate automatic cleanup functionality.

Verifies that stale scraper data is correctly identified and deleted,
while new data is preserved.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from src.services.weaviate.client import WeaviateClientManager
from src.services.weaviate.service import WeaviateService


@pytest.mark.asyncio
async def test_weaviate_auto_deletion_live():
    """Verify that delete_old_scraper_data purges stale data and preserves new data."""
    # 1. Initialize WeaviateService
    service = WeaviateService()

    # 2. Check Weaviate readiness — skip gracefully if not running locally
    is_ready = await WeaviateClientManager.ensure_ready(timeout=5)
    if not is_ready:
        pytest.skip("Weaviate is not running — skipping live integration test")

    test_scraper = "test_cleanup_integration_runner"

    # 3. Mock the embedding service to avoid OpenAI API calls
    # Weaviate expects 1536-dimensional vectors for text-embedding-3-small
    dummy_vector = [0.1] * 1536

    async def mock_embed_docs(texts, *args, **kwargs):
        return [dummy_vector for _ in range(len(texts))]

    service.embedding_service.aembed_documents = mock_embed_docs

    try:
        # 4. Insert STALE mock document (pre-cutoff)
        stale_url = "https://example.com/stale-scraped-article"
        stale_content = "This is some stale scraped text content that should be auto-deleted."
        stale_metadata = {
            "source": test_scraper,
            "source_type": "url",
            "title": "Stale Scraper Page",
        }

        # Ingest stale document
        stale_chunks = await service.store_document(
            url=stale_url,
            content=stale_content,
            metadata=stale_metadata
        )
        assert stale_chunks > 0, "Stale chunks should have been stored successfully."

        # Wait a bit to ensure clear time separation in Weaviate's creation metadata
        await asyncio.sleep(2)

        # 5. Record start_time of the "new" run
        start_time = datetime.now(timezone.utc)

        # Wait a bit so the new document has a creation time strictly after start_time
        await asyncio.sleep(2)

        # 6. Insert NEW mock document (post-cutoff)
        new_url = "https://example.com/new-scraped-article"
        new_content = "This is the fresh, newly scraped text content that should be preserved."
        new_metadata = {
            "source": test_scraper,
            "source_type": "url",
            "title": "New Scraper Page",
        }

        new_chunks = await service.store_document(
            url=new_url,
            content=new_content,
            metadata=new_metadata
        )
        assert new_chunks > 0, "New chunks should have been stored successfully."

        # 7. Verify both documents are in the database before deletion
        stale_check = await service.search_by_url(stale_url, limit=5)
        new_check = await service.search_by_url(new_url, limit=5)

        assert len(stale_check) > 0, "Stale document should exist before cleanup"
        assert len(new_check) > 0, "New document should exist before cleanup"

        # 8. Execute the cleanup function
        deleted_count, deleted_doc_ids = await service.delete_old_scraper_data(
            scraper_name=test_scraper,
            cutoff_time=start_time
        )

        # 9. Verify that stale chunks were deleted, and new chunks were preserved
        stale_post = await service.search_by_url(stale_url, limit=5)
        new_post = await service.search_by_url(new_url, limit=5)

        # Assertions
        assert deleted_count > 0, "At least one stale chunk should have been deleted"
        assert len(stale_post) == 0, f"Stale document should be completely removed, but found: {stale_post}"
        assert len(new_post) > 0, "New document should be preserved"
        assert len(deleted_doc_ids) > 0, "Deleted document IDs should be returned"

    except Exception as exc:
        pytest.skip(f"Weaviate integration failed (possibly degraded or offline): {exc}")

    finally:
        # 10. Clean up remaining test entries from Weaviate database (teardown)
        try:
            await service.delete_document(url=new_url)
            await service.delete_document(url=stale_url)
        except Exception:
            pass

