"""Embedding service."""

from typing import List

from langchain_openai import OpenAIEmbeddings

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

from .config import EMBEDDING_BATCH_SIZE

logger = get_logger(__name__)

class FallbackOpenAIEmbeddings:
    """Wrapper that tries primary FreeLLMAPI first, then falls back to OpenAI."""
    def __init__(self, primary: OpenAIEmbeddings, fallback: OpenAIEmbeddings):
        self.primary = primary
        self.fallback = fallback

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            return self.primary.embed_documents(texts)
        except Exception as e:
            logger.warning(f"Primary embeddings failed: {e}. Falling back to OpenAI.")
            return self.fallback.embed_documents(texts)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            return await self.primary.aembed_documents(texts)
        except Exception as e:
            logger.warning(f"Primary async embeddings failed: {e}. Falling back to OpenAI.")
            return await self.fallback.aembed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        try:
            return self.primary.embed_query(text)
        except Exception as e:
            logger.warning(f"Primary embed query failed: {e}. Falling back to OpenAI.")
            return self.fallback.embed_query(text)

    async def aembed_query(self, text: str) -> List[float]:
        try:
            return await self.primary.aembed_query(text)
        except Exception as e:
            logger.warning(f"Primary async embed query failed: {e}. Falling back to OpenAI.")
            return await self.fallback.aembed_query(text)

# FIX-004: In-process LRU cache for query embeddings.
# Embeddings are deterministic: same text → same vector. Safe to cache indefinitely.
# Capped at 5000 entries to avoid unbounded memory growth (~10 MB at 1536-dim float32).
_EMBED_QUERY_CACHE: dict[str, List[float]] = {}
_EMBED_CACHE_MAX = 5000


class EmbeddingService:
    """Wrapper for embedding generation with explicit batching."""

    def __init__(self):
        """Initialize embedding service."""
        primary_embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_base=settings.freellmapi_base_url,
            api_key=settings.freellmapi_key or "dummy-key",
        )
        fallback_embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
        self.embeddings = FallbackOpenAIEmbeddings(primary_embeddings, fallback_embeddings)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
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
                logger.error(f"Error embedding batch {i} to {i+len(batch)}: {e}")
                raise

        return results

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
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
                logger.error(f"Error embedding batch {i} to {i+len(batch)}: {e}")
                raise

        return results

    def embed_query(self, text: str) -> List[float]:
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
    async def aembed_query(self, text: str) -> List[float]:
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
