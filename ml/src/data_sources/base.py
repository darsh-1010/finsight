"""Abstract base class for data sources."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.documents import Document

from src.core.interfaces import IDataSource


class BaseDataSource(IDataSource, ABC):
    """Abstract base class defining the interface for all data sources.

    This provides a consistent interface for fetching and converting
    financial data from various sources (yfinance, Bloomberg, Alpha Vantage, etc.)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the data source."""

    @abstractmethod
    async def fetch(self, identifier: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch data based on a query.

        Args:
            identifier: The search identifier (e.g., ticker symbol)
            **kwargs: Additional parameters specific to the data source

        Returns:
            Dictionary containing the fetched data
        """

    @abstractmethod
    async def validate(self, identifier: str) -> bool:
        """Validate if a query/ticker is valid.

        Args:
            identifier: The identifier to validate

        Returns:
            True if valid, False otherwise
        """

    @abstractmethod
    def to_documents(self, data: dict[str, Any]) -> list[Document]:
        """Convert fetched data to LangChain Documents for vector storage.

        Args:
            data: The data fetched from the source

        Returns:
            List of LangChain Document objects
        """

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate that the data source connection is working.

        Returns:
            True if connection is valid, False otherwise
        """

    def get_metadata_template(self) -> dict[str, Any]:
        """Return common metadata fields for this source.

        Returns:
            Dictionary with common metadata fields
        """
        return {
            "source": self.name,
            "fetched_at": None,
        }
