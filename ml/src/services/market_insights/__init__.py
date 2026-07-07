"""Market Insights notification pipeline.

This package implements the event-driven, hybrid-RAG Market Insights system.
It detects market events via yfinance, retrieves context from the Vector DB,
classifies them using an LLM across 30 strict topics, and dispatches
alerts based on user tier entitlements.
"""

from src.services.market_insights.models import (AlertPayload, EventType,
                                                 InsightCategory,
                                                 InsightResult, InsightTopic,
                                                 MarketEvent)

__all__ = [
    "AlertPayload",
    "EventType",
    "InsightCategory",
    "InsightResult",
    "InsightTopic",
    "MarketEvent",
]
