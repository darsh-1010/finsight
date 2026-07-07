"""LLM Reasoning Engine for Market Insights classification.

Classifies a triggered MarketEvent + RAG context chunks into one of the
6 categories and 30 strict topics using OpenAI structured output.

Fallback logic:
  If the LLM signals insufficient context (confidence < threshold),
  a live Tavily web search is performed and the LLM is re-evaluated
  with the freshly retrieved results appended.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from src.llm.fallback_client import FallbackAsyncOpenAI
from pydantic import BaseModel, Field

from src.core.exceptions import LLMError
from src.services.market_insights.models import (InsightCategory,
                                                 InsightResult, InsightTopic,
                                                 MarketEvent)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Below this confidence the engine flags context_insufficient and tries fallback.
CONFIDENCE_FALLBACK_THRESHOLD = 0.55

# Model used for classification (fast + supports structured output).
_CLASSIFICATION_MODEL = os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini")

# Seconds to wait before Tavily results time out.
_TAVILY_TIMEOUT_SECONDS = 10

# System prompt shared across both the initial and fallback LLM calls.
_SYSTEM_PROMPT = """\
You are a senior financial analyst. Your job is to classify a triggered market
event into exactly ONE of the 30 pre-defined topics below.

CATEGORIES AND TOPICS:
Price Action       : Intraday Surge | Intraday Drop | 52-Week High | 52-Week Low | Volume Spike
Corporate Events   : Earnings Beat | Earnings Miss | Dividend Change | M&A Activity | Executive Change
Macroeconomic      : Interest Rate Impact | Inflation Data | GDP Revision | Employment Data | Trade Policy
Sector & Industry  : Sector Rotation | Regulatory Approval | Supply Chain Disruption | Commodity Price Move | Competitive Landscape Shift
Analyst Activity   : Rating Upgrade | Rating Downgrade | Price Target Raise | Price Target Cut | Coverage Initiation
Risk & Regulatory  : SEC Investigation | Regulatory Fine | Credit Rating Change | Short Interest Spike | Geopolitical Risk

RULES:
1. Return ONLY the category and topic values from the lists above.
2. Set context_insufficient = true ONLY if the provided context contains
   zero relevant information about the specific event.
3. confidence must be between 0.0 and 1.0.
4. summary must be a single concise sentence (max 20 words).
"""


# ──────────────────────────────────────────────────────────────────────────────
# Internal structured output schema (not exported)
# ──────────────────────────────────────────────────────────────────────────────


class _ClassificationOutput(BaseModel):
    """Strict schema the LLM must populate via structured output."""

    category: InsightCategory = Field(..., description="One of the 6 categories")
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str = Field(..., max_length=200)
    context_insufficient: bool = Field(default=False)


# ──────────────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────────────


class LLMEngine:
    """Classifies market events into the 30-topic taxonomy.

    Uses OpenAI beta structured output so the schema is enforced at the
    token-generation level — no post-hoc JSON parsing required.
    """

    def __init__(self, openai_api_key: str | None = None) -> None:
        """Initialise the engine with an optional API key override.

        Args:
            openai_api_key: OpenAI key; defaults to OPENAI_API_KEY env var.
        """
        self._client = FallbackAsyncOpenAI(
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        self._tavily_key: str | None = os.getenv("TAVILY_API_KEY")

    async def classify_event(
        self,
        event: MarketEvent,
        rag_chunks: list[dict],
    ) -> InsightResult:
        """Classify a market event using context + optional web-search fallback.

        Steps:
          1. Build user prompt from event + RAG chunks.
          2. Call OpenAI with structured output schema.
          3. If confidence < threshold, fetch Tavily results and re-classify.

        Args:
            event: The triggered MarketEvent.
            rag_chunks: Context chunks from the RAG layer (may be empty).

        Returns:
            Fully populated InsightResult.

        Raises:
            LLMError: When the OpenAI API fails on both attempts.
        """
        user_prompt = _build_user_prompt(event, rag_chunks)
        output = await self._call_llm(user_prompt)

        fallback_used = False
        if (
            output.context_insufficient
            or output.confidence < CONFIDENCE_FALLBACK_THRESHOLD
        ):
            logger.info(
                "[LLM_FALLBACK] Ticker: %s | Confidence: %.2f | Triggering web search",
                event.ticker,
                output.confidence,
            )
            web_results = await self._fetch_web_context(event)
            if web_results:
                enriched_prompt = _build_user_prompt(event, rag_chunks, web_results)
                output = await self._call_llm(enriched_prompt)
                fallback_used = True

        logger.info(
            "[LLM_RESULT] Ticker: %s | Topic: %s | Confidence: %.2f | Fallback: %s",
            event.ticker,
            output.topic.value,
            output.confidence,
            fallback_used,
        )
        return InsightResult(
            event=event,
            category=output.category,
            topic=output.topic,
            confidence=output.confidence,
            summary=output.summary,
            context_insufficient=output.context_insufficient,
            fallback_used=fallback_used,
        )

    async def _call_llm(self, user_prompt: str) -> _ClassificationOutput:
        """Invoke OpenAI structured output and return the parsed schema.

        Args:
            user_prompt: Full user-turn content for this classification call.

        Returns:
            Validated _ClassificationOutput instance.

        Raises:
            LLMError: On API failure or parse error.
        """
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=_CLASSIFICATION_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=_ClassificationOutput,
                temperature=0.1,
            )
            result: _ClassificationOutput | None = completion.choices[0].message.parsed
            if result is None:
                raise LLMError("LLM returned null structured output")
            return result
        except Exception as exc:
            logger.error("[LLM_ERROR] OpenAI call failed: %s", exc)
            raise LLMError(
                f"LLM classification failed: {exc}",
                details={"error": str(exc)},
            ) from exc

    async def _fetch_web_context(self, event: MarketEvent) -> list[dict[str, Any]]:
        """Fetch live web context via Tavily when RAG is insufficient.

        Falls back gracefully to an empty list when TAVILY_API_KEY is not set
        or when the request times out — the pipeline continues without it.

        Args:
            event: Source event used to build the search query.

        Returns:
            List of Tavily result dicts with keys: title, content, url.
        """
        if not self._tavily_key:
            logger.warning(
                "[TAVILY_SKIP] TAVILY_API_KEY not configured; skipping web search"
            )
            return []

        query = f"{event.ticker} stock {event.event_type.value.replace('_', ' ')} news today"
        try:
            results = await asyncio.wait_for(
                _call_tavily(self._tavily_key, query),
                timeout=_TAVILY_TIMEOUT_SECONDS,
            )
            logger.info(
                "[TAVILY_OK] Ticker: %s | Results: %d", event.ticker, len(results)
            )
            return results
        except asyncio.TimeoutError:
            logger.warning(
                "[TAVILY_TIMEOUT] Ticker: %s | Query timed out", event.ticker
            )
            return []
        except (ValueError, RuntimeError) as exc:
            logger.warning("[TAVILY_ERROR] Ticker: %s | Error: %s", event.ticker, exc)
            return []


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────


def _build_user_prompt(
    event: MarketEvent,
    rag_chunks: list[dict],
    web_results: list[dict[str, Any]] | None = None,
) -> str:
    """Build the full user-turn prompt for the LLM classification call.

    Args:
        event: The triggered market event.
        rag_chunks: Chunks from the Vector DB (may be empty).
        web_results: Optional Tavily results appended during fallback.

    Returns:
        Formatted multi-section prompt string.
    """
    sections: list[str] = [
        "=== MARKET EVENT ===",
        f"Ticker      : {event.ticker}",
        f"Event Type  : {event.event_type.value}",
        f"Price       : {event.current_price:.4f}",
        f"Change      : {event.price_change_pct:+.2f}%",
    ]
    if event.open_price:
        sections.append(f"Open        : {event.open_price:.4f}")
    if event.week_52_high:
        sections.append(f"52W High    : {event.week_52_high:.4f}")
    if event.week_52_low:
        sections.append(f"52W Low     : {event.week_52_low:.4f}")

    sections.append("\n=== RESEARCH CONTEXT (from Vector DB) ===")
    if rag_chunks:
        for idx, chunk in enumerate(rag_chunks, start=1):
            content = chunk.get("content", "")[:600]
            sections.append(f"[Chunk {idx}] {content}")
    else:
        sections.append("No relevant context found in Vector DB.")

    if web_results:
        sections.append("\n=== LIVE WEB SEARCH RESULTS ===")
        for result in web_results[:3]:
            title = result.get("title", "")
            content = result.get("content", "")[:400]
            url = result.get("url", "")
            sections.append(f"- {title}\n  {content}\n  Source: {url}")

    sections.append(
        "\nBased on the event and context above, classify into exactly ONE topic."
    )
    return "\n".join(sections)


async def _call_tavily(api_key: str, query: str) -> list[dict[str, Any]]:
    """Perform a Tavily search bounded to the last 4 hours of news.

    Uses httpx rather than the tavily SDK to avoid a hard dependency.

    Args:
        api_key: Tavily API key.
        query: Search query string.

    Returns:
        List of result dicts with title, content, url keys.
    """
    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "days": 1,  # Only last 24 hours of news
        "include_answer": False,
    }
    async with httpx.AsyncClient(timeout=8.0) as http_client:
        response = await http_client.post(
            "https://api.tavily.com/search",
            json=payload,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    return data.get("results", [])
