"""Embedding service."""

from typing import Any

from config.settings import settings
from src.llm.litellm_router import get_embedding_model_group, get_llm_router
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

from .config import EMBEDDING_BATCH_SIZE

logger = get_logger(__name__)


def _extract_vectors(response: Any) -> list[list[float]]:
    """Pull the raw float vectors out of a litellm EmbeddingResponse."""
    vectors = []
    for item in response.data:
        vectors.append(item["embedding"] if isinstance(item, dict) else item.embedding)
    return vectors


class FallbackOpenAIEmbeddings:
    """Embeddings via the shared litellm Router (FreeLLMAPI-primary, OpenAI-fallback).

    Keeps the exact method names/signatures the rest of the app already
    depends on (embed_documents/embed_query, sync and async) - callers need
    no changes.
    """

    def __init__(self, model: str) -> None:
        self._model_group = get_embedding_model_group(model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = get_llm_router().embedding(model=self._model_group, input=texts)
        return _extract_vectors(response)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await get_llm_router().aembedding(
            model=self._model_group, input=texts
        )
        return _extract_vectors(response)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> list[float]:
        vectors = await self.aembed_documents([text])
        return vectors[0]


# FIX-004: In-process LRU cache for query embeddings.
# Embeddings are deterministic: same text → same vector. Safe to cache indefinitely.
# Capped at 5000 entries to avoid unbounded memory growth (~10 MB at 1536-dim float32).
_EMBED_QUERY_CACHE: dict[str, list[float]] = {}
_EMBED_CACHE_MAX = 5000


class EmbeddingService:
    """Wrapper for embedding generation with explicit batching."""

    def __init__(self):
        """Initialize embedding service."""
        self.embeddings = FallbackOpenAIEmbeddings(settings.embedding_model)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts asynchronously.

        Using explicit batching to avoid OpenAI token limits (8192 tokens per request).
        """
        results = []
        total = len(texts)

        logger.debug(
            f"Generating embeddings for {total} texts in batches of {EMBEDDING_BATCH_SIZE}..."
        )

        for i in range(0, total, EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            try:
                # Use langchain's async method
                batch_embeddings = await self.embeddings.aembed_documents(batch)
                results.extend(batch_embeddings)
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(f"Error embedding batch {i} to {i + len(batch)}: {e}")
                raise

        return results

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts synchronously.
        """
        results = []
        total = len(texts)

        for i in range(0, total, EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            try:
                batch_embeddings = self.embeddings.embed_documents(batch)
                results.extend(batch_embeddings)
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(f"Error embedding batch {i} to {i + len(batch)}: {e}")
                raise

        return results

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text (cached).

        Cache key is normalised (lowercased + stripped) so that
        'HDFC Bank ' and 'hdfc bank' share the same cached vector.
        """
        cache_key = text.lower().strip()
        if cache_key in _EMBED_QUERY_CACHE:
            logger.debug("[EMBED_CACHE] HIT: %d chars", len(text))
            return _EMBED_QUERY_CACHE[cache_key]
        result = self.embeddings.embed_query(text)
        if len(_EMBED_QUERY_CACHE) < _EMBED_CACHE_MAX:
            _EMBED_QUERY_CACHE[cache_key] = result
        return result

    @timed("embedding.aembed_query", warn_threshold_s=1.0)
    async def aembed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text asynchronously (cached).

        Cache key is normalised (lowercased + stripped) so that
        'HDFC Bank ' and 'hdfc bank' share the same cached vector.
        """
        cache_key = text.lower().strip()
        if cache_key in _EMBED_QUERY_CACHE:
            logger.debug("[EMBED_CACHE] HIT (async): %d chars", len(text))
            return _EMBED_QUERY_CACHE[cache_key]
        result = await self.embeddings.aembed_query(text)
        if len(_EMBED_QUERY_CACHE) < _EMBED_CACHE_MAX:
            _EMBED_QUERY_CACHE[cache_key] = result
        return result
