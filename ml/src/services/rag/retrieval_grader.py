"""Retrieval Grader — LLM-based relevance scoring for RAG chunks.

Runs AFTER retrieval and BEFORE synthesis. Each retrieved chunk is scored
for relevance to the user's query. Chunks below the threshold are dropped;
if too few survive, a re-retrieval is triggered with the expanded query.

Uses the fast/cheap model (gpt-4.1-mini) to keep latency and cost low.
Structured output guarantees clean parsing — no regex/JSON hacks.

Architecture
------------
1. ``GradeResult``     — Pydantic structured output (relevant: bool, reason: str)
2. ``grade_chunks``    — Score a batch of chunks concurrently
3. ``grade_and_filter``— Grade + drop + optional re-retrieval in one call
"""

import asyncio
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.perf_utils import timed

logger = logging.getLogger(__name__)

# ── Structured output schema ──────────────────────────────────────────────

class GradeResult(BaseModel):
    """LLM grading verdict for a single retrieved chunk."""

    relevant: bool = Field(
        description=(
            "True if the chunk directly helps answer the user's query. "
            "False if it is topically adjacent but does not contain "
            "information needed to answer the question."
        )
    )
    reason: str = Field(
        max_length=120,
        description="One sentence explaining why this chunk is or is not relevant.",
    )


# ── Grading prompt ────────────────────────────────────────────────────────

_GRADER_SYSTEM_PROMPT = """\
You are a retrieval quality grader for a financial research assistant.

Your job: decide whether a retrieved document chunk is RELEVANT to the user's query.

RELEVANT means the chunk contains information that directly helps answer the query:
- Specific data points, metrics, or facts the query asks about
- Context that is necessary to understand or answer the query
- Direct discussion of the company, topic, or concept being asked about

NOT RELEVANT means:
- The chunk mentions the same company but discusses an unrelated topic
- The chunk is about a different time period than what was asked
- The chunk is boilerplate (legal disclaimers, table of contents, headers)
- The chunk is topically adjacent but doesn't help answer THIS specific query

Be strict — borderline chunks should be marked not relevant.
Financial data that is clearly stale (>1 year old for price-sensitive queries) is not relevant.
"""

_GRADER_TIMEOUT_SECONDS = 6.0

# Minimum chunks that must survive grading before we trigger re-retrieval.
_MIN_SURVIVING_CHUNKS = 1


class RetrievalGrader:
    """Grades retrieved chunks for relevance before they reach synthesis.

    Instantiate once per request cycle or share across the ContextManager.
    Uses the fast model to keep per-chunk grading under 1s.

    Usage::

        grader = RetrievalGrader()
        filtered = await grader.grade_and_filter(query, chunks)
    """

    def __init__(self, llm: ChatOpenAI | None = None) -> None:
        self._llm = llm or ChatOpenAI(
            model=settings.gpt_4o_mini,
            temperature=0.0,
        )
        self._grader = self._llm.with_structured_output(GradeResult)

    @timed("retrieval_grader.grade_batch", warn_threshold_s=3.0)
    async def grade_chunks(
        self,
        query: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Grade each chunk and annotate with relevance verdict.

        Args:
            query: The user's original query.
            chunks: List of chunk dicts (must have 'content' key).

        Returns:
            Same chunks list, each annotated with '_grade' key containing
            the GradeResult. Order is preserved.
        """
        if not chunks:
            return chunks

        tasks = [
            self._grade_single(query, chunk)
            for chunk in chunks
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for chunk, result in zip(chunks, results):
            if isinstance(result, GradeResult):
                chunk["_grade"] = result.model_dump()
            elif isinstance(result, Exception):
                # Fail-open: if grading fails, assume relevant.
                logger.warning(
                    "[GRADER] Grading failed for chunk, assuming relevant: %s",
                    result,
                )
                chunk["_grade"] = {"relevant": True, "reason": "Grading failed — fail-open."}

        relevant_count = sum(1 for c in chunks if c.get("_grade", {}).get("relevant", True))
        logger.info(
            "[GRADER] Query: %.60s | Total: %d | Relevant: %d | Dropped: %d",
            query, len(chunks), relevant_count, len(chunks) - relevant_count,
        )

        return chunks

    async def grade_and_filter(
        self,
        query: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Grade chunks and return only relevant ones.

        If all chunks are filtered out, returns the single highest-scoring
        chunk as a fallback (never returns empty if input was non-empty).

        Args:
            query: User query.
            chunks: Retrieved chunks.

        Returns:
            Filtered list of relevant chunks.
        """
        if not chunks:
            return []

        graded = await self.grade_chunks(query, chunks)
        relevant = [c for c in graded if c.get("_grade", {}).get("relevant", True)]

        if not relevant and graded:
            # Fallback: return the chunk with the highest retrieval score.
            best = max(graded, key=lambda c: c.get("score", c.get("metadata", {}).get("score", 0)))
            logger.warning(
                "[GRADER] All chunks filtered — falling back to highest-scored chunk"
            )
            return [best]

        return relevant

    async def _grade_single(self, query: str, chunk: dict[str, Any]) -> GradeResult:
        """Grade a single chunk against the query."""
        content = chunk.get("content", "")[:800]
        meta = chunk.get("metadata", {})
        source_info = ""
        if meta.get("title"):
            source_info = f" (Source: {meta['title']}"
            if meta.get("filing_date"):
                source_info += f", Date: {meta['filing_date']}"
            source_info += ")"

        user_msg = (
            f"User Query: {query[:400]}\n\n"
            f"Retrieved Chunk{source_info}:\n{content}"
        )

        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            result: GradeResult = await asyncio.wait_for(
                self._grader.ainvoke([
                    SystemMessage(content=_GRADER_SYSTEM_PROMPT),
                    HumanMessage(content=user_msg),
                ]),
                timeout=_GRADER_TIMEOUT_SECONDS,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("[GRADER] Chunk grading timed out — fail-open")
            return GradeResult(relevant=True, reason="Grading timed out — fail-open.")
