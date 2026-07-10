"""Tests for the current RAG service contract."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.exceptions import RAGError
from src.services.rag.rag_service import RAGService


@dataclass
class FakeSearchResult:
    """Minimal stand-in for Weaviate search results."""

    payload: dict
    score: float

    def model_dump(self) -> dict:
        """Return the serialized payload expected by the service."""
        return self.payload


class TestRAGService:
    """Test cases for the current RAG service implementation."""

    def test_init(self, mock_vector_store):
        """The service should keep the injected vector service instance."""
        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()

        assert rag_service.vector_service == mock_vector_store

    @pytest.mark.asyncio
    async def test_retrieve_context_success(self, mock_vector_store, sample_query):
        """Only results above the configured threshold should be returned."""
        mock_vector_store.search_similar_by_source_type = AsyncMock(return_value=[
            FakeSearchResult(
                payload={"content": "Relevant content", "source_url": "https://example.com/relevant", "score": 0.85},
                score=0.85,
            ),
            FakeSearchResult(
                payload={"content": "Low score", "source_url": "https://example.com/low", "score": 0.10},
                score=0.10,
            ),
        ])

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            results = await rag_service.retrieve_context(sample_query, limit=3, min_score=0.40)

        assert len(results) == 1
        assert results[0]["content"] == "Relevant content"
        mock_vector_store.search_similar_by_source_type.assert_awaited_once_with(
            query=sample_query,
            limit=3,
            source_type="pdf",
            pre_computed_vector=None,
        )

    @pytest.mark.asyncio
    async def test_retrieve_context_failure(self, mock_vector_store, sample_query):
        """Runtime failures should be wrapped as RAG errors."""
        mock_vector_store.search_similar_by_source_type = AsyncMock(side_effect=RuntimeError("Connection error"))

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()

            with pytest.raises(RAGError, match="Connection error"):
                await rag_service.retrieve_context(sample_query)

    @pytest.mark.asyncio
    async def test_retrieve_article_context_uses_url_source_type(self, mock_vector_store, sample_query):
        """Article retrieval should query the URL-backed source type."""
        mock_vector_store.search_similar_by_source_type = AsyncMock(return_value=[
            FakeSearchResult(
                payload={"content": "Article content", "source_url": "https://example.com/article", "score": 0.70},
                score=0.70,
            ),
        ])

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            results = await rag_service.retrieve_article_context(sample_query, limit=2)

        assert len(results) == 1
        mock_vector_store.search_similar_by_source_type.assert_awaited_once_with(
            query=sample_query,
            limit=2,
            source_type="url",
        )

    @pytest.mark.asyncio
    async def test_store_document_new(self, mock_vector_store, sample_document):
        """New documents should be stored without deletion."""
        mock_vector_store.search_by_url = AsyncMock(return_value=[])
        mock_vector_store.store_document = AsyncMock(return_value=3)

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            chunks_stored = await rag_service.store_document(
                sample_document["url"],
                sample_document["content"],
                sample_document["metadata"],
            )

        assert chunks_stored == 3
        mock_vector_store.search_by_url.assert_awaited_once_with(sample_document["url"], limit=1)
        mock_vector_store.store_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_document_duplicate_skip(self, mock_vector_store, sample_document):
        """Duplicate documents should be skipped when replacement is disabled."""
        mock_vector_store.search_by_url = AsyncMock(return_value=[{"content": "Existing"}])
        mock_vector_store.store_document = AsyncMock()

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            chunks_stored = await rag_service.store_document(
                sample_document["url"],
                sample_document["content"],
                sample_document["metadata"],
                replace_existing=False,
            )

        assert chunks_stored == 0
        mock_vector_store.store_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_document_duplicate_replace(self, mock_vector_store, sample_document):
        """Duplicate documents should be deleted before replacement."""
        mock_vector_store.search_by_url = AsyncMock(return_value=[{"content": "Existing"}])
        mock_vector_store.delete_document = AsyncMock(return_value=True)
        mock_vector_store.store_document = AsyncMock(return_value=3)

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            chunks_stored = await rag_service.store_document(
                sample_document["url"],
                sample_document["content"],
                sample_document["metadata"],
                replace_existing=True,
            )

        assert chunks_stored == 3
        mock_vector_store.delete_document.assert_awaited_once_with(sample_document["url"])

    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_vector_store, sample_document):
        """URL deletion should delegate to the vector service."""
        mock_vector_store.delete_document = AsyncMock(return_value=True)

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            result = await rag_service.delete_document(sample_document["url"])

        assert result is True
        mock_vector_store.delete_document.assert_awaited_once_with(sample_document["url"])

    @pytest.mark.asyncio
    async def test_get_document_stats(self, mock_vector_store):
        """Stats should be returned directly from the vector service."""
        mock_vector_store.get_collection_stats = AsyncMock(return_value={"total_objects": 15})

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            stats = await rag_service.get_document_stats()

        assert stats["total_objects"] == 15

    @pytest.mark.asyncio
    async def test_check_duplicate_error_returns_false(self, mock_vector_store, sample_document):
        """Duplicate checks should fail open when the lookup errors."""
        mock_vector_store.search_by_url = AsyncMock(side_effect=RuntimeError("Search error"))

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            is_duplicate = await rag_service._check_duplicate(sample_document["url"])

        assert is_duplicate is False

    def test_close(self, mock_vector_store):
        """Closing the service should close the vector service."""
        mock_vector_store.close = Mock()

        with patch("src.services.rag.rag_service.WeaviateService", return_value=mock_vector_store):
            rag_service = RAGService()
            rag_service.close()

        mock_vector_store.close.assert_called_once()
