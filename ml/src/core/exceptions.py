"""Centralized exception hierarchy for the application.

This ensures consistent error handling, clear stack traces, and
the ability to catch specific operational failures.
"""


class ChatbotException(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Alias for backward compatibility or future-proofing
AppError = ChatbotException


class ServiceError(AppError):
    """Raised when a service fails to perform its primary function."""


class ValidationError(AppError):
    """Raised when request validation fails."""


class RateLimitError(AppError):
    """Raised when API rate limits are exceeded."""


class DatabaseError(ServiceError):
    """Base class for database-related errors."""


class DatabaseConnectionError(DatabaseError):
    """Raised when a connection to a database or external service fails."""


class DataSourceError(AppError):
    """Base class for data source-related errors."""


class YFinanceError(DataSourceError):
    """Raised when yFinance data fetching fails."""


class RAGError(ServiceError):
    """Raised when document retrieval or ingestion fails."""


class QueryAnalysisError(ServiceError):
    """Raised when LLM-based query analysis fails."""


class TickerResolutionError(ServiceError):
    """Raised when ticker resolution fails or is highly ambiguous."""


class LLMError(AppError):
    """Raised when the LLM provider fails or returns invalid data."""
