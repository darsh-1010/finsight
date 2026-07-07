"""Core package - abstractions, types, and DI container."""

from src.core.container import Container, inject
from src.core.interfaces import (
    ICache,
    IChatService,
    IDataSource,
    ILLMClient,
    IQueryService,
    ITickerService,
)
from src.core.types import (
    DataQuality,
    IntentCategory,
    JsonDict,
    QueryId,
    SessionId,
    TickerSymbol,
    ValidationStatus,
)

__all__ = [
    # Interfaces
    "ILLMClient",
    "IDataSource",
    "IQueryService",
    "ITickerService",
    "IChatService",
    "ICache",
    # Types
    "JsonDict",
    "TickerSymbol",
    "QueryId",
    "SessionId",
    "IntentCategory",
    "DataQuality",
    "ValidationStatus",
    # DI
    "Container",
    "inject",
]
