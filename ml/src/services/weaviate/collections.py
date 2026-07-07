"""Collection management for Weaviate."""

from typing import Any

import weaviate.classes.config as wvc
from weaviate.collections import Collection

from src.services.schema.weaviate_schema import WeaviateSchema
from src.utils.logger import get_logger

from .client import WeaviateClientManager
from .config import COLLECTION_NAME

logger = get_logger(__name__)


class CollectionManager:
    """Manages Weaviate collections and schema."""

    @staticmethod
    def ensure_collection(
        name: str = COLLECTION_NAME,
        schema_class: Any = WeaviateSchema,
        force_recreate: bool = False,
    ) -> Collection:
        """
        Ensure the collection exists with the correct schema.
        Creates it if it doesn't exist.
        """
        client = WeaviateClientManager.get_client()

        if force_recreate and client.collections.exists(name):
            logger.warning(f"Forcing recreation of collection '{name}'...")
            client.collections.delete(name)

        if not client.collections.exists(name):
            logger.info(
                f"[COLLECTION_SETUP] Creating a new knowledge collection '{name}' with canonical schema. "
                "This initializes the structure required for storing and retrieving high-dimensional vector data."
            )

            # Get schema properties from provided definition
            properties = schema_class.get_schema()

            try:
                # Create collection with manual vectorizer (we generate embeddings ourselves)
                collection = client.collections.create(
                    name=name,
                    properties=properties,
                    vectorizer_config=wvc.Configure.Vectorizer.none(),
                    vector_index_config=schema_class.get_vector_index_config(),
                    # Stable inverted index configuration
                    inverted_index_config=wvc.Configure.inverted_index(
                        index_timestamps=True,
                        index_null_state=False,
                        index_property_length=False,
                    ),
                )
                logger.info(
                    f"[COLLECTION_READY] Collection '{name}' created successfully. "
                    "The AI system's storage is now initialized and ready to receive data."
                )
                return collection
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(f"Failed to create collection '{name}': {e}")
                raise
        else:
            # logger.debug(f"Collection '{name}' already exists.")
            return client.collections.get(name)

    @staticmethod
    def get_collection(name: str = COLLECTION_NAME) -> Collection:
        """Get the collection object."""
        client = WeaviateClientManager.get_client()
        return client.collections.get(name)
