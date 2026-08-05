"""Knowledge Graph Service — high-level API for graph-backed queries.

Orchestrates CypherGenerator + GraphClient to answer relational questions.
Degrades gracefully when Neo4j is unavailable (returns empty context).

Integration point: called from ContextManager when the query analysis
detects a relational/multi-hop intent.
"""

import asyncio
from typing import Any

from src.services.knowledge_graph.cypher_generator import CypherGenerator
from src.services.knowledge_graph.graph_client import GraphClient
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

logger = get_logger(__name__)

# Max records we'll format into LLM context.
_MAX_CONTEXT_RECORDS = 15


class GraphService:
    """High-level graph query service for the chat pipeline.

    Usage::

        svc = GraphService()
        context, citations = await svc.query("Who are Nvidia's competitors?")
        # context is a formatted string ready for the LLM prompt.
        # citations is a list of source dicts for the frontend.
    """

    def __init__(self) -> None:
        self._client = GraphClient()
        self._generator = CypherGenerator()
        self._available: bool | None = None  # Lazy health check result.

    async def is_available(self) -> bool:
        """Check if Neo4j is reachable. Caches result for the session."""
        if self._available is None:
            self._available = await self._client.health_check()
            if not self._available:
                logger.info("[GRAPH_SVC] Neo4j not available — graph queries disabled")
        return self._available

    @timed("graph_service.query", warn_threshold_s=5.0)
    async def query(
        self,
        user_query: str,
        *,
        ticker_hint: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Answer a relational query using the knowledge graph.

        Args:
            user_query: Natural-language question.
            ticker_hint: Optional ticker context from the session.

        Returns:
            Tuple of (formatted context string, citations list).
            Returns (None, []) if graph is unavailable, query doesn't
            need graph, or no results are found.
        """
        if not await self.is_available():
            return None, []

        # Step 1: Generate Cypher.
        cypher_result = await self._generator.generate(
            user_query, ticker_hint=ticker_hint
        )

        if cypher_result is None:
            return None, []

        if not cypher_result.requires_graph:
            logger.info("[GRAPH_SVC] Query does not require graph traversal — skipping")
            return None, []

        # Step 2: Execute Cypher.
        records = await self._client.execute(cypher_result.cypher)

        if not records:
            logger.info("[GRAPH_SVC] No graph results for: %.80s", user_query)
            return None, []

        # Step 3: Format results into LLM-consumable context.
        context = self._format_context(records, cypher_result.explanation)
        citations = [{
            "source": "knowledge_graph",
            "data_type": "graph_traversal",
            "title": f"Knowledge Graph: {cypher_result.explanation[:80]}",
            "confidence": 0.9,
        }]

        logger.info(
            "[GRAPH_SVC] Returned %d records for graph query", len(records)
        )
        return context, citations

    async def close(self) -> None:
        """Release the Neo4j connection."""
        await self._client.close()

    def _format_context(
        self,
        records: list[dict[str, Any]],
        explanation: str,
    ) -> str:
        """Format graph query results into a markdown-style context block."""
        capped = records[:_MAX_CONTEXT_RECORDS]

        lines = [f"[Knowledge Graph Result — {explanation}]"]

        if not capped:
            return ""

        # Auto-detect columns from the first record.
        columns = list(capped[0].keys())

        # Build a simple markdown table.
        header = " | ".join(str(col) for col in columns)
        separator = " | ".join("---" for _ in columns)
        lines.append(f"| {header} |")
        lines.append(f"| {separator} |")

        for record in capped:
            row = " | ".join(_format_cell(record.get(col)) for col in columns)
            lines.append(f"| {row} |")

        if len(records) > _MAX_CONTEXT_RECORDS:
            lines.append(f"\n(Showing {_MAX_CONTEXT_RECORDS} of {len(records)} results)")

        return "\n".join(lines)


def _format_cell(value: Any) -> str:
    """Format a single cell value for display."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, dict):
        # Neo4j node properties come as dicts.
        name = value.get("name") or value.get("ticker") or str(value)
        return str(name)
    return str(value)
