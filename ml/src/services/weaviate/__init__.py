"""
Weaviate Service Package.

Provides a modular, production-ready interface to Weaviate vector database.
"""

from .client import WeaviateClientManager
from .service import WeaviateService

__all__ = ["WeaviateService", "WeaviateClientManager"]
