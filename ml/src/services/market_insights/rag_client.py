"""RAG & Data Retrieval Layer for the Market Insights pipeline.

Wraps the existing WeaviateService to retrieve the top-5 most semantically
relevant, recently-scraped text chunks for a triggered ticker event.
The query is built from the event type and ticker to maximise recall.
"""

from __future__ import annotations

from src.services.market_insights.models import EventType, MarketEvent
from src.services.weaviate.service import WeaviateService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum chunks returned per event — keeps LLM context tight.
_DEFAULT_CHUNK_LIMIT = 5

# Minimum semantic similarity score before a chunk is included.
_MIN_RELEVANCE_SCORE = 0.40


class MarketInsightsRAGClient:
    """Retrieves Vector DB context for a triggered market event.

    Reuses the shared WeaviateService so no second DB connection is opened.
    """

    def __init__(self) -> None:
        """Initialise with a fresh WeaviateService connection."""
        self._vector_service = WeaviateService()
        logger.info("[RAG_INIT] MarketInsightsRAGClient ready")

    async def get_recent_context(
        self,
        event: MarketEvent,
        hours_back: int = 24,
        limit: int = _DEFAULT_CHUNK_LIMIT,
    ) -> list[dict]:
        """Retrieve the top-N most relevant chunks for a market event.

        Builds a rich natural-language query from the ticker + event type so
        the embedding search surfaces the most useful scraped content.

        Args:
            event: The triggered MarketEvent to retrieve context for.
            hours_back: Ignored in the current implementation — Weaviate
                        returns freshest results by default ranking.
                        Preserved as a parameter for future time-filtering.
            limit: Maximum number of chunks to return (default 5).

        Returns:
            List of chunk dicts with keys: content, score, metadata.
            Empty list when nothing relevant is found.
        """
        query = _build_rag_query(event)
        logger.info(
            "[RAG_QUERY] Ticker: %s | EventType: %s | HoursBack: %d",
            event.ticker,
            event.event_type.value,
            hours_back,
        )

        try:
            raw_results = await self._vector_service.search_similar(
                query=query,
                limit=limit,
            )
        except Exception as exc:
            logger.warning(
                "[RAG_FALLBACK] Vector search failed for %s. Falling back to empty context. Error: %s",
                event.ticker,
                exc,
            )
            return []

        chunks = _filter_and_serialise(raw_results, _MIN_RELEVANCE_SCORE)
        logger.info(
            "[RAG_RESULT] Ticker: %s | Chunks: %d",
            event.ticker,
            len(chunks),
        )
        return chunks

    def close(self) -> None:
        """Release the underlying Weaviate connection."""
        try:
            self._vector_service.close()
            logger.info("[RAG_CLOSE] MarketInsightsRAGClient connection closed")
        except (TypeError, AttributeError, RuntimeError) as exc:
            logger.warning("[RAG_CLOSE_WARN] Could not close cleanly: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────


def _build_rag_query(event: MarketEvent) -> str:
    """Compose a natural-language RAG query from the event context.

    A richer query string improves embedding recall for the specific event
    rather than returning generic company overviews.

    Args:
        event: Source MarketEvent.

    Returns:
        Natural-language query string for the vector search.
    """
    event_descriptions: dict[EventType, str] = {
        EventType.INTRADAY_DROP: (
            f"{event.ticker} stock intraday drop price decline "
            f"{abs(event.price_change_pct):.1f}% sell-off news catalyst"
        ),
        EventType.INTRADAY_SURGE: (
            f"{event.ticker} stock intraday surge rally "
            f"{event.price_change_pct:.1f}% gain news catalyst"
        ),
        EventType.WEEK_52_HIGH: (
            f"{event.ticker} 52-week high all-time high breakout momentum "
            f"price target analyst"
        ),
        EventType.WEEK_52_LOW: (
            f"{event.ticker} 52-week low support level bearish outlook "
            f"earnings risk downgrade"
        ),
        EventType.VOLUME_SPIKE: (
            f"{event.ticker} unusual volume spike trading activity "
            f"institutional interest news event"
        ),
        EventType.CORPORATE_ACTION: (
            f"{event.ticker} corporate action earnings report dividend change split mergers "
            f"acquisition calendar"
        ),
        EventType.ANALYST_EVENT: (
            f"{event.ticker} analyst recommendation rating upgrade downgrade coverage initiation "
            f"price target target price"
        ),
        EventType.NEWS_CATALYST: (
            f"{event.ticker} news catalyst macroeconomic sector regulatory risk sec investigation "
            f"geopolitical trade policy inflation interest rate"
        ),
    }
    return event_descriptions.get(
        event.event_type,
        f"{event.ticker} market news financial analysis",
    )


def _filter_and_serialise(raw_results: list, min_score: float) -> list[dict]:
    """Filter chunks below the relevance threshold and serialise to dicts.

    Args:
        raw_results: List of SearchResult objects from WeaviateService.
        min_score: Minimum score to retain a chunk.

    Returns:
        List of plain dicts ready for the LLM prompt.
    """
    chunks: list[dict] = []
    for result in raw_results:
        score: float = getattr(result, "score", 0.0)
        if score < min_score:
            continue
        if hasattr(result, "model_dump"):
            chunks.append(result.model_dump())
        else:
            chunks.append({"content": str(result), "score": score})
    return chunks
