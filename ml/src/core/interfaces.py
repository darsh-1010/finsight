"""Abstract interfaces for dependency injection.

These interfaces define contracts for services, enabling
loose coupling and testability.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class ILLMClient(ABC):
    """Interface for LLM client implementations."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate a text response from the LLM."""

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type, **kwargs) -> Any:
        """Generate a structured response matching the schema."""

    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream response chunks from the LLM."""
        yield ""  # Required for AsyncGenerator


class IDataSource(ABC):
    """Interface for data source implementations."""

    @abstractmethod
    async def fetch(self, identifier: str, **kwargs) -> dict[str, Any]:
        """Fetch data for a given identifier."""

    @abstractmethod
    async def validate(self, identifier: str) -> bool:
        """Validate that the identifier exists."""


class IQueryService(ABC):
    """Interface for query analysis service."""

    @abstractmethod
    async def analyze(self, query: str) -> dict[str, Any]:
        """Analyze and expand a user query."""

    @abstractmethod
    async def analyze_and_fetch(self, query: str) -> dict[str, Any]:
        """Full pipeline: analyze query and fetch data."""

    @abstractmethod
    def build_llm_context(
        self,
        expansion: Any,
        contexts: list[Any],
        max_context_chars: int | None = None,
    ) -> str:
        """Build a formatted LLM context string for a response."""


class ITickerService(ABC):
    """Interface for ticker resolution service."""

    @abstractmethod
    async def resolve(self, name: str, context: str = "") -> dict[str, Any]:
        """Resolve a company name to a ticker symbol."""

    @abstractmethod
    async def resolve_multiple(
        self, names: list[str], context: str = ""
    ) -> list[dict[str, Any]]:
        """Resolve multiple company names in parallel."""


class IChatService(ABC):
    """Interface for chat service."""

    @abstractmethod
    async def chat(
        self, message: str, session_id: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Process a chat message and return response."""

    @abstractmethod
    async def stream(
        self, message: str, session_id: str | None = None, **kwargs
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat response."""
        yield {}

    @abstractmethod
    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""

    @abstractmethod
    async def get_conversation_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation history in chatbot-standard format.

        Returns:
            List of messages with {role, content, timestamp} format.
        """


class IRAGService(ABC):
    """Interface for RAG (Retrieval-Augmented Generation) service."""

    @abstractmethod
    async def retrieve_context(
        self, query: str, limit: int | None = None, filters: dict | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve relevant document chunks for a query.

        Args:
            query: Search query
            limit: Maximum number of documents to return
            filters: Optional metadata filters

        Returns:
            List of document results with content, metadata, and scores
        """

    @abstractmethod
    async def store_document(
        self, url: str, content: str, metadata: dict | None = None
    ) -> int:
        """Store document in vector database.

        Args:
            url: Document URL (for deduplication)
            content: Document text content
            metadata: Optional metadata (title, author, etc.)

        Returns:
            Number of chunks created
        """

    @abstractmethod
    async def delete_document(self, url: str) -> bool:
        """Delete document from vector database.

        Args:
            url: Document URL to delete

        Returns:
            True if deleted, False if not found
        """

    @abstractmethod
    async def delete_document_by_id(self, document_id: str) -> bool:
        """Delete document from vector database by its unique identifier.

        Args:
            document_id: Unique document identifier to delete

        Returns:
            True if deleted, False if not found
        """


class ICache(ABC):
    """Interface for cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with optional TTL."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
