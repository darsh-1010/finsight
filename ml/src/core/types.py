"""Type definitions and type aliases for the application."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

# Type aliases for common patterns
JsonDict: TypeAlias = dict[str, Any]
TickerSymbol: TypeAlias = str
QueryId: TypeAlias = str
SessionId: TypeAlias = str


class IntentCategory(str, Enum):
    """Categories for query intent classification."""

    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    DECISION = "decision"
    INFORMATION = "information"
    FORECAST = "forecast"


class DataQuality(str, Enum):
    """Data quality levels for financial context."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class ValidationStatus(str, Enum):
    """Validation status for ticker resolution."""

    VALIDATED = "validated"
    UNVALIDATED = "unvalidated"
    FAILED = "failed"


@dataclass(frozen=True)
class YFinanceEndpoint:
    """Represents a yFinance endpoint configuration."""

    name: str
    fields: tuple[str, ...]
    time_range: str | None = None


# Common yFinance endpoints
YFINANCE_ENDPOINTS = {
    "info": YFinanceEndpoint(
        "info", ("sector", "industry", "marketCap", "currentPrice")
    ),
    "financials": YFinanceEndpoint(
        "financials", ("Total Revenue", "Net Income", "Gross Profit")
    ),
    "balance_sheet": YFinanceEndpoint("balance_sheet", ("Total Assets", "Total Debt")),
    "cashflow": YFinanceEndpoint("cashflow", ("Free Cash Flow", "Operating Cash Flow")),
    "history": YFinanceEndpoint("history", ("Open", "High", "Low", "Close", "Volume")),
    "recommendations": YFinanceEndpoint(
        "recommendations", ("strongBuy", "buy", "hold", "sell")
    ),
}
