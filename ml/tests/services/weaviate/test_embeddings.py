"""Tests for FallbackOpenAIEmbeddings (litellm-backed embeddings)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.weaviate.embeddings import FallbackOpenAIEmbeddings


def _mock_embedding_response(vectors: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.data = [{"embedding": v} for v in vectors]
    return response


def test_embed_documents_extracts_vectors():
    embeddings = FallbackOpenAIEmbeddings("text-embedding-3-small")

    with patch("src.services.weaviate.embeddings.get_llm_router") as mock_get_router:
        mock_router = MagicMock()
        mock_router.embedding.return_value = _mock_embedding_response([[0.1, 0.2], [0.3, 0.4]])
        mock_get_router.return_value = mock_router

        result = embeddings.embed_documents(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    called_model = mock_router.embedding.call_args.kwargs["model"]
    assert called_model == "freellmapi/text-embedding-3-small"


@pytest.mark.asyncio
async def test_aembed_query_returns_single_vector():
    embeddings = FallbackOpenAIEmbeddings("text-embedding-3-small")

    with patch("src.services.weaviate.embeddings.get_llm_router") as mock_get_router:
        mock_router = MagicMock()
        mock_router.aembedding = AsyncMock(return_value=_mock_embedding_response([[0.5, 0.6]]))
        mock_get_router.return_value = mock_router

        result = await embeddings.aembed_query("hello")

    assert result == [0.5, 0.6]
