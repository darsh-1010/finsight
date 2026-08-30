from typing import Any

from config.settings import settings
from src.core.exceptions import RAGError
from src.core.interfaces import IRAGService
from src.services.weaviate.service import WeaviateService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAGService(IRAGService):
    """RAG service implementing IRAGService interface."""

    def __init__(self):
        """Initialize RAG service."""
        self.vector_service = WeaviateService()
        logger.info("RAGService initialized")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        self.close()

    async def retrieve_context(
        self,
        query: str,
        limit: int | None = None,
        filters: list[Any] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents for a query.

        Args:
            query: Search query
            limit: Maximum number of documents to return
            filters: Optional metadata filters (list of weaviate Filter objects)
            **kwargs:
                min_score: Optional minimum relevance score override
                pre_computed_vector: Optional pre-batched embedding

        Returns:
            List of relevant documents with metadata
        """
        try:
            effective_limit = limit or kwargs.get("limit") or settings.rerank_top_k
            min_score = kwargs.get("min_score") or settings.min_document_relevance_score
            effective_filters = filters or kwargs.get("filters")
            pre_computed_vector = kwargs.get("pre_computed_vector")

            logger.info(f"Retrieving context for query: {query[:100]}...")

            # Use advanced filtering if multiple filters are provided
            if effective_filters:
                results = await self.vector_service.search_similar_with_filters(
                    query=query,
                    limit=effective_limit,
                    filters=effective_filters,
                    pre_computed_vector=pre_computed_vector,
                )
            else:
                # Default to PDF source type for generic context
                results = await self.vector_service.search_similar_by_source_type(
                    query=query,
                    limit=effective_limit,
                    source_type="pdf",
                    pre_computed_vector=pre_computed_vector,
                )

            # Apply relevance score threshold
            filtered_results = [r for r in results if r.score >= min_score]
            dropped = len(results) - len(filtered_results)
            if dropped > 0:
                logger.info(
                    f"Filtered out {dropped} chunks below relevance threshold ({min_score})"
                )

            return [r.model_dump() for r in filtered_results]

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
            raise RAGError(f"RAG retrieval failed: {e}") from e

    async def retrieve_article_context(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant research articles.

        Args:
            query: Search query
            **kwargs: limit, min_score
        """
        try:
            limit = kwargs.get("limit") or settings.rerank_top_k
            min_score = kwargs.get("min_score") or settings.min_article_relevance_score

            logger.info(f"Retrieving article context for query: {query[:100]}...")

            results = await self.vector_service.search_similar_by_source_type(
                query=query,
                limit=limit,
                source_type="url",
            )

            filtered_results = [r for r in results if r.score >= min_score]
            return [r.model_dump() for r in filtered_results]

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
            raise RAGError(f"RAG retrieval failed: {e}") from e

    async def store_document(
        self,
        url: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> int:
        """Store document with proper metadata and deduplication.

        Args:
            url: Document URL (used for deduplication)
            content: Document content
            metadata: Document metadata (title, author, created_date, etc.)
            replace_existing: If True, delete existing document before storing
            **kwargs: Additional arguments passed to vector_service

        Returns:
            Number of chunks stored

        Raises:
            Exception: If storage fails
        """
        try:
            meta = metadata or {}

            # Check for duplicates by URL
            existing = await self._check_duplicate(url)

            if existing:
                if replace_existing:
                    logger.info("Document exists, deleting before re-storing")
                    await self.delete_document(url)
                else:
                    logger.info(f"Document already exists, skipping: {url}")
                    return 0

            logger.info(
                f"Storing document: {url} with metadata: {meta.get('title', 'N/A')}"
            )

            chunks_stored = await self.vector_service.store_document(
                url=url,
                content=content,
                metadata=meta,
                **kwargs,
            )

            logger.info(
                f"[KNOWLEDGE_UPDATE] Successfully updated the AI's intelligence with {chunks_stored} new chunks "
                f"from '{url}'. This specific knowledge source is now live and searchable."
            )
            return chunks_stored

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error storing document: {str(e)}", exc_info=True)
            raise RAGError(f"RAG storage failed: {e}") from e

    async def delete_document(self, url: str) -> bool:
        """Delete document by URL.

        Args:
            url: Document URL to delete

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If deletion fails
        """
        try:
            logger.info(f"Deleting document by URL: {url}")

            success = await self.vector_service.delete_document(url)

            if success:
                logger.info(
                    f"[KNOWLEDGE_REMOVAL] Successfully purged '{url}' from the AI system. "
                    "This information has been removed to maintain accuracy and prevent outdated responses."
                )
            else:
                logger.warning(
                    f"[KNOWLEDGE_MISS] Attempted to delete '{url}', but it was not found in the database. "
                    "No changes were made."
                )

            return success

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error deleting document by URL: {str(e)}", exc_info=True)
            raise RAGError(f"RAG deletion failed: {e}") from e

    async def delete_document_by_id(self, document_id: str) -> bool:
        """Delete document by document_id.

        Args:
            document_id: Unique document identifier

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If deletion fails
        """
        try:
            logger.info(f"Deleting document by document_id: {document_id}")

            success = await self.vector_service.delete_document(
                url="",
                document_id=document_id,  # Not used for document_id deletion
            )

            if success:
                logger.info(f"Successfully deleted document: {document_id}")
            else:
                logger.warning(f"Document not found for deletion: {document_id}")

            return success

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error deleting document by ID: {str(e)}", exc_info=True)
            raise RAGError(f"RAG deletion failed: {e}") from e

    async def delete_documents_by_metadata(self, filters: dict[str, Any]) -> int:
        """Delete documents matching metadata filters.

        Args:
            filters: Dictionary of metadata field -> value to match
                    Example: {"author": "John Doe", "organization": "acme-corp"}

        Returns:
            Number of documents deleted

        Raises:
            Exception: If deletion fails
        """
        try:
            logger.info(f"Deleting documents matching filters: {filters}")

            deleted_count = await self.vector_service.delete_document_by_metadata(
                filters
            )

            logger.info(
                f"[BULK_KNOWLEDGE_SYNC] Successfully removed {deleted_count} documents matching specialized filters. "
                "This synchronization ensures the database contains only relevant, authorized content."
            )
            return deleted_count

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(
                f"Error deleting documents by metadata: {str(e)}", exc_info=True
            )
            raise

    async def update_document_metadata(
        self, document_id: str, updates: dict[str, Any]
    ) -> bool:
        """Update metadata for a document.

        Args:
            document_id: Unique document identifier
            updates: Dictionary of metadata fields to update
                    Example: {"title": "New Title", "author": "New Author"}

        Returns:
            True if update successful

        Raises:
            Exception: If update fails
        """
        try:
            logger.info(f"Updating metadata for document_id: {document_id}")

            success = await self.vector_service.update_document_metadata(
                document_id=document_id, updates=updates
            )

            if success:
                logger.info(
                    f"[ATTR_UPDATE] Successfully refreshed attributes for document '{document_id}'. "
                    "This ensures that all information sourced from this document has the most current metadata."
                )
            else:
                logger.warning(
                    f"[ATTR_MISS] Could not find document '{document_id}' to update. "
                    "The system knowledge base was not modified."
                )

            return success

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error updating document metadata: {str(e)}", exc_info=True)
            raise

    async def get_document_stats(self) -> dict[str, Any]:
        """Get statistics about stored documents.

        Returns:
            Dictionary with document statistics

        Raises:
            Exception: If stats retrieval fails
        """
        try:
            stats = await self.vector_service.get_collection_stats()

            logger.info(f"Retrieved document stats: {stats}")
            return stats

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error getting document stats: {str(e)}", exc_info=True)
            raise

    async def _check_duplicate(self, url: str) -> bool:
        """Check if document already exists by URL.

        Returns:
            True if document exists, False otherwise
        """
        try:
            # Search for exact URL match
            results = await self.vector_service.search_by_url(url, limit=1)
            return len(results) > 0

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error checking duplicate by URL: {str(e)}", exc_info=True)
            # If we can't check, assume it's not a duplicate
            return False

    def close(self):
        """Close RAG service connections."""
        try:
            self.vector_service.close()
            logger.info("RAGService closed")
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error closing RAGService: {str(e)}", exc_info=True)
