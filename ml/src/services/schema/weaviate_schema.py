"""Weaviate schema definition for DocumentChunks collection.

This module defines the complete Weaviate schema structure for storing
and managing document chunks with embeddings and metadata.
"""

import weaviate.classes.config as wvc
from weaviate.classes.config import DataType, Property, Tokenization


class WeaviateSchema:
    """Weaviate schema definition for the DocumentChunks collection."""

    COLLECTION_NAME = "DocumentChunks"
    VECTORIZER = "none"  # LangChain controls embeddings

    @staticmethod
    def get_vector_index_config():
        """Get HNSW index configuration.

        Optimized for stability on resource-constrained environments.
        """
        return wvc.Configure.VectorIndex.hnsw(
            distance_metric=wvc.VectorDistances.COSINE,
            ef_construction=32,  # Minimal complexity for low-resource environments
            max_connections=8,  # Minimal connections to prevent starvation
            ef=-1,  # Dynamic
        )

    @staticmethod
    def get_schema():
        """Get the complete schema configuration for DocumentChunks collection.

        Returns:
            list: List of Property objects for schema creation
        """
        return [
            # Content (vectorized)
            Property(
                name="content",
                data_type=DataType.TEXT,
                description="Document chunk text content (vectorized)",
                skip_vectorization=False,  # This will be vectorized
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            # Document metadata
            Property(
                name="source_url",
                data_type=DataType.TEXT,
                description="URL source of the document",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,  # Harmonized: prevents strategy mismatch
                tokenization=Tokenization.FIELD,  # Exact match (stable roaringset)
            ),
            Property(
                name="document_id",
                data_type=DataType.TEXT,
                description="Unique identifier for the document",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,  # Harmonized: prevents strategy mismatch
                tokenization=Tokenization.FIELD,  # Exact match (stable roaringset)
            ),
            Property(
                name="chunk_index",
                data_type=DataType.INT,
                description="Position of chunk within document (0-based)",
                skip_vectorization=True,
                index_filterable=True,
                index_range_filters=True,
            ),
            # Content classification
            Property(
                name="source_type",
                data_type=DataType.TEXT,
                description="Type of source (pdf, url, etc.)",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="source",
                data_type=DataType.TEXT,
                description="Name of the scraper or source identifier (e.g. 'morgan_stanley')",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="extraction_method",
                data_type=DataType.TEXT,
                description="Method used to extract text (pypdf2_pdfplumber, etc.)",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="language",
                data_type=DataType.TEXT,
                description="Language code (en, es, fr, etc.)",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="category",
                data_type=DataType.TEXT,
                description="Content category",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="tags",
                data_type=DataType.TEXT_ARRAY,
                description="List of tags assigned to the chunk",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,  # Harmonized: prevents strategy mismatch
                tokenization=Tokenization.FIELD,
            ),
            # Document info
            Property(
                name="summary",
                data_type=DataType.TEXT,
                description="Summary of the content (e.g., video transcript)",
                skip_vectorization=False,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="title",
                data_type=DataType.TEXT,
                description="Document title",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="author",
                data_type=DataType.TEXT,
                description="Document author",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="page_count",
                data_type=DataType.INT,
                description="Total pages in original document",
                skip_vectorization=True,
                index_filterable=True,
                index_range_filters=True,
            ),
            Property(
                name="file_size",
                data_type=DataType.INT,
                description="File size in bytes",
                skip_vectorization=True,
                index_filterable=True,
                index_range_filters=True,
            ),
            # Timestamps
            Property(
                name="created_date",
                data_type=DataType.DATE,
                description="Document creation date (ISO8601)",
                skip_vectorization=True,
                index_filterable=True,
                index_range_filters=True,
            ),
            Property(
                name="modified_date",
                data_type=DataType.DATE,
                description="Document last modified date (ISO8601)",
                skip_vectorization=True,
                index_filterable=True,
                index_range_filters=True,
            ),
            # Access control
            Property(
                name="uploaded_by",
                data_type=DataType.TEXT,
                description="User who uploaded the document",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="organization",
                data_type=DataType.TEXT,
                description="Organization/team owning the document",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            # Searchable fields for text search
            Property(
                name="title_searchable",
                data_type=DataType.TEXT,
                description="Searchable title field",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="author_searchable",
                data_type=DataType.TEXT,
                description="Searchable author field",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="source_searchable",
                data_type=DataType.TEXT,
                description="Searchable source field",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="content_searchable",
                data_type=DataType.TEXT,
                description="Searchable content field",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            # User upload scoping
            Property(
                name="user_id",
                data_type=DataType.TEXT,
                description="User identifier for scoping retrieved chunks",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="session_id",
                data_type=DataType.TEXT,
                description="Session identifier for scoping retrieved chunks",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.FIELD,
            ),
            # Provenance enrichment (Tier 4)
            Property(
                name="publication_date",
                data_type=DataType.TEXT,
                description="ISO date of publication",
                skip_vectorization=True,
                index_filterable=False,
                index_searchable=False,
            ),
            Property(
                name="source_name",
                data_type=DataType.TEXT,
                description="Human-readable source name",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=True,
                tokenization=Tokenization.WORD,
            ),
            Property(
                name="source_domain",
                data_type=DataType.TEXT,
                description="Domain-level source identification",
                skip_vectorization=True,
                index_filterable=True,
                index_searchable=False,
                tokenization=Tokenization.FIELD,
            ),
        ]
