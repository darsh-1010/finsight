"""Tests for the knowledge graph service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.knowledge_graph.cypher_generator import CypherQuery
from src.services.knowledge_graph.graph_service import GraphService, _format_cell


class TestFormatCell:
    """Tests for the cell formatter helper."""

    def test_none_value(self):
        assert _format_cell(None) == "—"

    def test_float_value(self):
        assert _format_cell(3.14159) == "3.14"

    def test_string_value(self):
        assert _format_cell("AAPL") == "AAPL"

    def test_dict_value_with_name(self):
        assert _format_cell({"name": "Apple Inc.", "ticker": "AAPL"}) == "Apple Inc."


class TestGraphService:
    """Tests for the GraphService orchestrator."""

    @pytest.mark.asyncio
    async def test_query_unavailable(self):
        """Should return (None, []) when Neo4j is unavailable."""
        svc = GraphService.__new__(GraphService)
        svc._client = MagicMock()
        svc._client.health_check = AsyncMock(return_value=False)
        svc._generator = MagicMock()
        svc._available = None

        ctx, cits = await svc.query("Who are Nvidia's competitors?")
        assert ctx is None
        assert cits == []

    @pytest.mark.asyncio
    async def test_query_not_graph_needed(self):
        """Should return (None, []) when the query doesn't need graph."""
        svc = GraphService.__new__(GraphService)
        svc._client = MagicMock()
        svc._client.health_check = AsyncMock(return_value=True)
        svc._available = None

        cypher_result = CypherQuery(
            cypher="MATCH (c:Company) RETURN c",
            explanation="Simple lookup",
            requires_graph=False,
        )
        svc._generator = MagicMock()
        svc._generator.generate = AsyncMock(return_value=cypher_result)

        ctx, cits = await svc.query("What is Apple's stock price?")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Should return formatted context when graph has results."""
        svc = GraphService.__new__(GraphService)
        svc._client = MagicMock()
        svc._client.health_check = AsyncMock(return_value=True)
        svc._client.execute = AsyncMock(return_value=[
            {"competitor": "AMD", "ticker": "AMD", "sector": "Technology"},
            {"competitor": "Intel", "ticker": "INTC", "sector": "Technology"},
        ])
        svc._available = None

        cypher_result = CypherQuery(
            cypher="MATCH (c:Company {ticker: 'NVDA'})-[:COMPETES_WITH]->(comp) RETURN comp",
            explanation="Nvidia's competitors",
            requires_graph=True,
        )
        svc._generator = MagicMock()
        svc._generator.generate = AsyncMock(return_value=cypher_result)

        ctx, cits = await svc.query("Who are Nvidia's competitors?")
        assert ctx is not None
        assert "AMD" in ctx
        assert "Intel" in ctx
        assert len(cits) == 1
        assert cits[0]["source"] == "knowledge_graph"

    @pytest.mark.asyncio
    async def test_query_no_results(self):
        """Should return (None, []) when graph returns no records."""
        svc = GraphService.__new__(GraphService)
        svc._client = MagicMock()
        svc._client.health_check = AsyncMock(return_value=True)
        svc._client.execute = AsyncMock(return_value=[])
        svc._available = None

        cypher_result = CypherQuery(
            cypher="MATCH (c:Company {ticker: 'ZZZ'})-[:COMPETES_WITH]->(comp) RETURN comp",
            explanation="Unknown company competitors",
            requires_graph=True,
        )
        svc._generator = MagicMock()
        svc._generator.generate = AsyncMock(return_value=cypher_result)

        ctx, cits = await svc.query("Who are ZZZ's competitors?")
        assert ctx is None
        assert cits == []
