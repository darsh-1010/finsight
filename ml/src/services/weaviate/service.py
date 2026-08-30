"""Weaviate Service implementation."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, HybridFusion, MetadataQuery
from weaviate.exceptions import WeaviateQueryError

from src.core.exceptions import RAGError
from src.core.models import SearchResult
from src.services.schema.weaviate_schema import WeaviateSchema
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

from .client import WeaviateClientManager
from .collections import CollectionManager
from .config import BATCH_SIZE, COLLECTION_NAME
from .embeddings import EmbeddingService

logger = get_logger(__name__)


class WeaviateService:
    """
    Main service for interacting with Weaviate vector database.
    Handles document chunking, embedding, storage, and retrieval.
    """

    def __init__(self):
        """Initialize Weaviate service components."""
        self.embedding_service = EmbeddingService()
        self.collection_manager = CollectionManager
        # Ensure schema on startup (lazy check)
        self._schema_ensured = False

    async def _ensure_resources(
        self,
        collection_name: str = COLLECTION_NAME,
        schema_class: Any = WeaviateSchema,
    ) -> None:
        """Ensure Weaviate is ready and schema exists with all properties.
        Args:
            collection_name: The name of the collection to check.
            schema_class: The schema class containing the source of truth.
        """
        await WeaviateClientManager.ensure_ready()
        self.collection_manager.ensure_collection(collection_name, schema_class)
        # Idempotently add missing properties to existing collection
        new_props = schema_class.get_schema()
        await self._add_missing_properties(collection_name, new_props)

    async def _add_missing_properties(
        self, collection_name: str, new_props: list[Any]
    ) -> None:
        """Idempotently add missing properties to an existing collection."""
        client = WeaviateClientManager.get_client()
        existing = client.collections.get(collection_name)
        existing_config = await asyncio.to_thread(existing.config.get)
        existing_prop_names = {p.name for p in existing_config.properties}
        for prop in new_props:
            if prop.name not in existing_prop_names:
                await asyncio.to_thread(existing.config.add_property, prop)
                logger.info("[SCHEMA_MIGRATION] Added property: %s", prop.name)

    async def store_document(
        self,
        url: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> int:
        """Store a document in Weaviate.
        Args:
            url: Document URL/Identifier
            content: Document text content
            metadata: Additional metadata. 'source_type' key controls auto chunk sizing.
            **kwargs: Configuration overrides (chunk_size, chunk_overlap, collection_name).
        Returns:
            The number of chunks stored.
        """
        collection_name = kwargs.get("collection_name", COLLECTION_NAME)
        await self._ensure_resources(
            collection_name, kwargs.get("schema_class", WeaviateSchema)
        )
        logger.info(
            f"[KNOWLEDGE_STORAGE] Starting ingestion for: {url}. "
            f"This process chunks and embeds the document to update the AI's knowledge base."
        )
        try:
            # 1. Prepare Metadata
            meta = metadata or {}
            # Prioritise provided document ID from metadata; fall back to URL-based UUID
            doc_id = str(
                meta.get("document_id")
                or meta.get("doc_id")
                or uuid.uuid5(uuid.NAMESPACE_URL, url)
            )
            # 2. Select chunk strategy — document-type-aware
            splitter, eff_size, eff_overlap = self._create_splitter(
                source_type=meta.get("source_type", "other"),
                chunk_size=kwargs.get("chunk_size", 0),
                chunk_overlap=kwargs.get("chunk_overlap", 0),
            )
            logger.info(
                "[CHUNK] %s | source_type=%s -> chunk_size=%d, overlap=%d",
                url,
                meta.get("source_type", "other"),
                eff_size,
                eff_overlap,
            )
            chunks = self._chunk_document_with_splitter(
                content=content,
                metadata=meta,
                url=url,
                splitter=splitter,
                config=(eff_size, eff_overlap),
            )
            if not chunks:
                logger.warning(f"No chunks created for document: {url}")
                return 0
            stored_count = await self._embed_and_ingest(
                chunks=chunks,
                doc_id=doc_id,
                url=url,
                meta=meta,
                collection_name=collection_name,
            )
            logger.info(
                f"[KNOWLEDGE_STORAGE_COMPLETE] Successfully stored {stored_count} chunks for {url}. "
                f"The AI is now updated with the latest content from this document."
            )
            return stored_count
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to store document {url}: {e}", exc_info=True)
            raise

    async def _embed_and_ingest(
        self,
        *,
        chunks: list[str],
        doc_id: str,
        url: str,
        meta: dict[str, Any],
        collection_name: str,
    ) -> int:
        """Generate embeddings and ingest chunks into Weaviate."""
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        vectors = await self.embedding_service.aembed_documents(chunks)
        logger.info(
            f"Ingesting {len(chunks)} chunks into Weaviate collection '{collection_name}'..."
        )
        return await self._ingest_chunks_batch(
            chunks=chunks,
            vectors=vectors,
            doc_metadata={
                "doc_id": doc_id,
                "url": url,
                "base_metadata": meta,
            },
            collection_name=collection_name,
        )

    def _create_splitter(
        self,
        *,
        source_type: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[RecursiveCharacterTextSplitter, int, int]:
        """Create a local text splitter with document-type-aware sizes."""
        _chunk_strategy = {
            "pdf": (1500, 200),
            "url": (600, 80),
            "video": (500, 100),
            "user_upload": (1500, 200),
        }
        default_size, default_overlap = _chunk_strategy.get(source_type, (1000, 150))
        effective_chunk_size = chunk_size if chunk_size > 0 else default_size
        effective_chunk_overlap = (
            chunk_overlap if chunk_overlap > 0 else default_overlap
        )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=effective_chunk_size,
            chunk_overlap=effective_chunk_overlap,
            length_function=len,
        )
        return splitter, effective_chunk_size, effective_chunk_overlap

    def _chunk_document_with_splitter(
        self,
        *,
        content: str,
        metadata: dict[str, Any],
        url: str,
        splitter: RecursiveCharacterTextSplitter,
        config: tuple[int, int],
    ) -> list[str]:
        """Chunk document content using a caller-provided splitter."""
        csize, coverlap = config
        logger.info("[CHUNKING_START] Source: %s | Length: %d", url, len(content))
        docs = splitter.create_documents(texts=[content], metadatas=[metadata])
        chunks = [d.page_content for d in docs]
        logger.info(
            "[CHUNK_STATS] Chunks: %d | Size: %d | Overlap: %d",
            len(chunks),
            csize,
            coverlap,
        )
        return chunks

    async def _ingest_chunks_batch(
        self,
        *,
        chunks: list[str],
        vectors: list[list[float]],
        doc_metadata: dict[str, Any],
        **kwargs: Any,
    ) -> int:
        """Ingest chunks using explicit batching with insert_many.
        Args:
            chunks: List of text chunks.
            vectors: List of embedding vectors.
            doc_metadata: Contains doc_id, url, and base_metadata.
            **kwargs: batch_size, max_retries, collection_name.
        """
        batch_size = kwargs.get("batch_size", BATCH_SIZE)
        max_retries = kwargs.get("max_retries", 3)
        collection_name = kwargs.get("collection_name", COLLECTION_NAME)
        collection = self.collection_manager.get_collection(collection_name)
        total_stored = 0
        total_chunks = len(chunks)
        # Prepare objects using helper
        objects_to_insert = self._create_data_objects(
            chunks=chunks,
            vectors=vectors,
            doc_metadata=doc_metadata,
        )
        logger.info(
            f"[BATCH_PREPARE] Prepared {total_chunks} data objects for Weaviate. "
            f"Ready to store content in batches of {batch_size}."
        )
        # Process in batches with retry logic
        for i in range(0, total_chunks, batch_size):
            batch_objects = objects_to_insert[i : i + batch_size]
            inserted = await self._insert_batch_with_retry(
                collection, batch_objects, i, total_chunks, max_retries
            )
            total_stored += inserted
        return total_stored

    def _create_data_objects(
        self,
        *,
        chunks: list[str],
        vectors: list[list[float]],
        doc_metadata: dict[str, Any],
    ) -> list[Any]:
        """Create Weaviate DataObjects from chunks."""
        doc_id = doc_metadata["doc_id"]
        url = doc_metadata["url"]
        base_metadata = doc_metadata["base_metadata"]
        objects = []
        current_time = datetime.utcnow().isoformat() + "Z"
        for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            props = {
                "content": chunk_text,
                "document_id": doc_id,
                "source_url": url,
                "chunk_index": i,
                "created_date": current_time,
                **base_metadata,
            }
            objects.append(
                DataObject(
                    properties=props,
                    vector=vector,
                    uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_chunk_{i}")),
                )
            )
        return objects

    async def _insert_batch_with_retry(
        self,
        collection: Any,
        batch_objects: list[Any],
        batch_idx: int,
        _total_chunks: int,
        max_retries: int,
    ) -> int:
        """Insert a single batch with retry logic."""
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = await asyncio.to_thread(
                    collection.data.insert_many, batch_objects
                )
                stored = 0
                if response.has_errors:
                    for idx, err in response.errors.items():
                        logger.error(
                            "Error inserting chunk %d: %s", batch_idx + idx, err
                        )
                    stored = len(batch_objects) - len(response.errors)
                else:
                    stored = len(batch_objects)
                logger.info(
                    f"[BATCH_SUCCESS] Successfully stored {stored} fragments from batch starting at index {batch_idx}. "
                    "Data is being processed and integrated into the AI's long-term memory."
                )
                return stored
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                retry_count += 1
                logger.warning("Batch insertion attempt %d failed: %s", retry_count, e)
                if retry_count >= max_retries:
                    logger.error(
                        "Batch insertion failed after %d attempts", max_retries
                    )
                    raise RAGError(f"Failed to ingest document chunks: {e}") from e
                await asyncio.sleep(2**retry_count)
        return 0

    @staticmethod
    def _parse_query_response(response: Any) -> list[SearchResult]:
        """Normalize Weaviate query response objects to a standardized SearchResult list."""
        results = []
        for obj in response.objects:
            doc_id = obj.properties.get("document_id")
            if doc_id:
                doc_id = str(doc_id)
            score = getattr(obj.metadata, "score", None)
            if score is None:
                certainty = getattr(obj.metadata, "certainty", None)
                if certainty is not None:
                    score = certainty
                else:
                    score = 1.0 - (getattr(obj.metadata, "distance", 0.5) or 0.5)
            results.append(
                SearchResult(
                    content=str(obj.properties.get("content", "")),
                    source_url=obj.properties.get("source_url"),
                    document_id=doc_id,
                    chunk_index=obj.properties.get("chunk_index"),
                    score=float(score),
                    metadata=obj.properties,
                )
            )
        return results

    @timed("weaviate.search_similar", warn_threshold_s=1.0)
    async def search_similar(
        self, query: str, limit: int = 10, collection_name: str = COLLECTION_NAME
    ) -> list[SearchResult]:
        """
        Search for similar documents using vector similarity.
        """
        await self._ensure_resources(collection_name)
        try:
            # Generate query embedding (used as the vector component of hybrid search)
            vector = await self.embedding_service.aembed_query(query)
            collection = self.collection_manager.get_collection(collection_name)
            # Hybrid search: 75% vector + 25% BM25.
            # BM25 improves precision for financial keywords (ticker symbols, metric names,
            # e.g. 'EBITDA', 'P/E', 'HDFCBANK') that vector search may under-weight.
            # Schema already has index_searchable=True + Tokenization.WORD on 'content'.
            # No re-ingestion required — this is a query-layer-only change.
            try:
                response = await asyncio.to_thread(
                    lambda: collection.query.hybrid(
                        query=query,
                        vector=vector,
                        alpha=0.75,  # 75% vector, 25% BM25
                        fusion_type=HybridFusion.RELATIVE_SCORE,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True),
                    )
                )
            except WeaviateQueryError:
                logger.warning(
                    "[WEAVIATE_SEARCH_FALLBACK] Hybrid query failed, falling back to near_vector search."
                )
                response = await asyncio.to_thread(
                    lambda: collection.query.near_vector(
                        near_vector=vector,
                        limit=limit,
                        return_metadata=MetadataQuery(certainty=True, distance=True),
                    )
                )
            return self._parse_query_response(response)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise RAGError(f"Vector search failed: {e}") from e

    @timed("weaviate.search_by_source_type", warn_threshold_s=1.0)
    async def search_similar_by_source_type(
        self,
        query: str,
        limit: int = 10,
        *,
        source_type: str = "pdf",
        collection_name: str = COLLECTION_NAME,
        pre_computed_vector: list[float] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents, filtered by source_type (e.g. 'pdf' or 'url').
        Args:
            pre_computed_vector: Optional pre-batched embedding. When provided, skips the
                internal aembed_query() call (saves one OpenAI round-trip ~300ms).
                Used by context_manager batch embedding optimisation (Fix #6).
        """
        await self._ensure_resources(collection_name)
        try:
            # Use pre-computed vector if provided; otherwise compute one (fallback).
            vector = pre_computed_vector or await self.embedding_service.aembed_query(
                query
            )
            collection = self.collection_manager.get_collection(collection_name)
            # Build source_type pre-filter (applied inside Weaviate engine, not post-hoc)
            where_filter = Filter.by_property("source_type").equal(source_type)
            # Hybrid search with source_type pre-filter.
            # alpha=0.75: 75% vector (semantic) + 25% BM25 (keyword precision).
            # BM25 is especially useful for source-typed searches where users ask about
            # specific metrics (e.g. 'quarterly revenue' in docs vs 'PE ratio' in articles).
            try:
                response = await asyncio.to_thread(
                    lambda: collection.query.hybrid(
                        query=query,
                        vector=vector,
                        alpha=0.75,
                        fusion_type=HybridFusion.RELATIVE_SCORE,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True),
                    )
                )
            except WeaviateQueryError:
                logger.warning(
                    "[WEAVIATE_SEARCH_FALLBACK] Hybrid source type query failed, falling back to near_vector."
                )
                response = await asyncio.to_thread(
                    lambda: collection.query.near_vector(
                        near_vector=vector,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(certainty=True, distance=True),
                    )
                )
            return self._parse_query_response(response)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Filtered search failed: {e}", exc_info=True)
            raise RAGError(f"Vector filtered search failed: {e}") from e

    @timed("weaviate.search_with_filters", warn_threshold_s=1.0)
    async def search_similar_with_filters(
        self,
        query: str,
        limit: int,
        filters: list[Any],
        *,
        collection_name: str = COLLECTION_NAME,
        pre_computed_vector: list[float] | None = None,
    ) -> list[SearchResult]:
        """Search with arbitrary AND filters (used for user-upload scoped retrieval)."""
        await self._ensure_resources(collection_name)
        try:
            vector = pre_computed_vector or await self.embedding_service.aembed_query(
                query
            )
            collection = self.collection_manager.get_collection(collection_name)
            where_filter = Filter.all_of(filters)
            try:
                response = await asyncio.to_thread(
                    lambda: collection.query.hybrid(
                        query=query,
                        vector=vector,
                        alpha=0.75,
                        fusion_type=HybridFusion.RELATIVE_SCORE,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True),
                    )
                )
            except WeaviateQueryError:
                logger.warning(
                    "[WEAVIATE_SEARCH_FALLBACK] Hybrid filtered query failed, falling back to near_vector."
                )
                response = await asyncio.to_thread(
                    lambda: collection.query.near_vector(
                        near_vector=vector,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(certainty=True, distance=True),
                    )
                )
            return self._parse_query_response(response)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Multi-filter search failed: {e}", exc_info=True)
            raise RAGError(f"Vector multi-filter search failed: {e}") from e

    async def search_by_url(
        self, url: str, limit: int = 1, collection_name: str = COLLECTION_NAME
    ) -> list[dict[str, Any]]:
        """Search for chunks by their source URL."""
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        try:
            response = await asyncio.to_thread(
                lambda: collection.query.fetch_objects(
                    filters=Filter.by_property("source_url").equal(url), limit=limit
                )
            )
            return [
                {"content": obj.properties.get("content"), "metadata": obj.properties}
                for obj in response.objects
            ]
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Search by URL failed: {e}")
            return []

    async def delete_document(
        self,
        url: str = "",
        document_id: str = "",
        collection_name: str = COLLECTION_NAME,
    ) -> bool:
        """Delete document by URL or ID."""
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        try:
            if document_id:
                # Filter by document_id
                response = await asyncio.to_thread(
                    lambda: collection.data.delete_many(
                        where=Filter.by_property("document_id").equal(document_id)
                    )
                )
            elif url:
                # Filter by source_url
                response = await asyncio.to_thread(
                    lambda: collection.data.delete_many(
                        where=Filter.by_property("source_url").equal(url)
                    )
                )
            else:
                return False
            if response.successful:
                logger.info(
                    f"[DATA_PURGE] Document removal successful for {url if url else document_id}. "
                    "This content has been permanently cleared from the AI's search index."
                )
            return bool(response.successful)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Deletion failed: {e}", exc_info=True)
            return False

    async def delete_document_by_metadata(
        self, filters: dict[str, Any], collection_name: str = COLLECTION_NAME
    ) -> int:
        """Delete documents matching metadata filters."""
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        if not filters:
            return 0
        # Build filter
        filter_list = []
        for key, value in filters.items():
            filter_list.append(Filter.by_property(key).equal(value))
        if not filter_list:
            return 0
        if len(filter_list) == 1:
            where_filter = filter_list[0]
        else:
            where_filter = Filter.all_of(filter_list)
        try:
            response = await asyncio.to_thread(
                lambda: collection.data.delete_many(where=where_filter)
            )
            logger.info(
                f"[BULK_DELETE] Cleaned up {response.successful} chunks matching selective filters: {filters}. "
                f"This targeted removal in '{collection_name}' helps maintain a lean and relevant database."
            )
            return response.successful
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete documents by metadata: {e}")
            raise

    async def delete_old_scraper_data(
        self,
        scraper_name: str,
        cutoff_time: datetime,
        collection_name: str = COLLECTION_NAME,
    ) -> tuple[int, list[str]]:
        """Delete web scraped data for a specific scraper that is older than the cutoff time.
        Args:
            scraper_name: The source name of the scraper (e.g. 'morgan_stanley')
            cutoff_time: UTC datetime object representing the start of the current scrape
            collection_name: Target collection
        Returns:
            Tuple of (deleted chunk count, list of unique document_ids removed).
        """
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        try:
            # Only targets scraped-web chunks — never PDF uploads — for safety.
            where_filter = Filter.all_of(
                [
                    Filter.by_property("source_type").equal("url"),
                    Filter.by_property("source").equal(scraper_name),
                    Filter.by_creation_time().less_than(cutoff_time),
                ]
            )
            # Weaviate v4 Cursor API (after) does not support filtering (where).
            # To handle large datasets safely over limits, we use a drain-loop:
            # Fetch a batch -> record IDs -> delete that batch by UUID -> repeat.
            document_ids_set = set()
            total_deleted = 0
            while True:
                fetch_response = await asyncio.to_thread(
                    lambda: collection.query.fetch_objects(
                        filters=where_filter,
                        return_properties=["document_id"],
                        limit=2000,
                    )
                )
                if not fetch_response.objects:
                    break
                batch_uuids = []
                for obj in fetch_response.objects:
                    batch_uuids.append(obj.uuid)
                    doc_id = obj.properties.get("document_id")
                    if doc_id:
                        document_ids_set.add(str(doc_id))
                if not batch_uuids:
                    break
                # Delete this specific batch by their physical UUIDs
                delete_response = await asyncio.to_thread(
                    lambda uuids=batch_uuids: collection.data.delete_many(
                        where=Filter.by_id().contains_any(uuids)
                    )
                )
                total_deleted += delete_response.successful
                # Safety break out if deletion fails to progress
                if delete_response.successful == 0:
                    logger.warning(
                        "[WEAVIATE_CLEANUP] Failed to delete batch UUIDs, breaking drain loop "
                        "to avoid infinite hang."
                    )
                    break
            document_ids = list(document_ids_set)
            logger.info(
                "[WEAVIATE_CLEANUP] Routinely removed %d old data chunks (source='%s', older than %s). "
                "This cleanup ensures the AI doesn't retrieve outdated information. Unique docs synchronized: %d",
                total_deleted,
                scraper_name,
                cutoff_time.isoformat(),
                len(document_ids),
            )
            return total_deleted, document_ids
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete old scraper data for {scraper_name}: {e}")
            raise

    async def update_document_metadata(
        self,
        document_id: str,
        updates: dict[str, Any],
        collection_name: str = COLLECTION_NAME,
    ) -> bool:
        """Update metadata for all chunks of a document."""
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        try:
            # Update all chunks with this document_id
            response = await asyncio.to_thread(
                lambda: collection.data.update_many(
                    where=Filter.by_property("document_id").equal(document_id),
                    data=updates,
                )
            )
            success = response.successful > 0
            if success:
                logger.info(
                    f"[METADATA_UPDATE] Successfully updated metadata for {response.successful} "
                    f"chunks of document {document_id}. This ensures the AI uses the most "
                    "current attribution and context for this specific record."
                )
            else:
                logger.warning(
                    f"[METADATA_MISS] No database entries found for document {document_id} "
                    f"in {collection_name}. The update was skipped as the document does not exist."
                )
            return success
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to update document metadata: {e}")
            raise

    async def get_collection_stats(
        self, collection_name: str = COLLECTION_NAME
    ) -> dict[str, Any]:
        """Get collection statistics."""
        await self._ensure_resources(collection_name)
        collection = self.collection_manager.get_collection(collection_name)
        try:
            # .aggregate.over_all is the v4 way
            response = await asyncio.to_thread(
                collection.aggregate.over_all, total_count=True
            )
            return {"total_count": response.total_count}
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def close(self):
        """Close connections."""
        WeaviateClientManager.close()
