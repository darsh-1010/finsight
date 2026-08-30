"""Cypher Query Generator — translates natural language to Cypher.

Uses an LLM (gpt-4.1-mini) with structured output to generate safe,
read-only Cypher queries for the financial knowledge graph.

Safety: Only SELECT-type queries are allowed. Any generated Cypher
containing write operations (CREATE, MERGE, SET, DELETE, DETACH,
REMOVE, DROP) is rejected.
"""

import asyncio
import logging
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config.settings import settings
from src.llm.litellm_router import get_chat_model
from src.utils.perf_utils import timed

logger = logging.getLogger(__name__)

# ── Structured output schema ──────────────────────────────────────────────


class CypherQuery(BaseModel):
    """Structured output from the Cypher generator."""

    cypher: str = Field(
        description=(
            "A valid, read-only Cypher query that answers the user's question "
            "using the knowledge graph schema. Must start with MATCH or OPTIONAL MATCH. "
            "Must NOT contain CREATE, MERGE, SET, DELETE, DETACH, REMOVE, or DROP."
        ),
    )
    explanation: str = Field(
        max_length=200,
        description="Brief explanation of what this query does and why.",
    )
    requires_graph: bool = Field(
        description=(
            "True if this question genuinely needs graph traversal "
            "(relationships between entities). False if it could be answered "
            "with a simple lookup or vector search."
        ),
    )


# ── System prompt ─────────────────────────────────────────────────────────

_CYPHER_SYSTEM_PROMPT = """\
You are a Cypher query generator for a financial knowledge graph in Neo4j.

## Graph Schema

### Nodes
- (:Company {ticker, name, sector, industry, market_cap, updated_at})
- (:Person {name, title, updated_at})
- (:Sector {name})
- (:Filing {type, date, accession_number, ticker})
- (:EarningsCall {date, quarter, fiscal_year, ticker})

### Relationships
- (Company)-[:COMPETES_WITH]->(Company)
- (Company)-[:SUPPLIES_TO]->(Company)
- (Company)-[:CUSTOMER_OF]->(Company)
- (Company)-[:SUBSIDIARY_OF]->(Company)
- (Person)-[:EXEC_OF]->(Company)
- (Company)-[:BELONGS_TO]->(Sector)
- (Company)-[:HAS_FILING]->(Filing)
- (Company)-[:HAS_EARNINGS]->(EarningsCall)
- (Company)-[:MENTIONED_IN {sentiment, context}]->(Filing|EarningsCall)

## Rules
1. Generate ONLY read-only queries (MATCH, OPTIONAL MATCH, RETURN, WHERE, ORDER BY, LIMIT).
2. NEVER generate CREATE, MERGE, SET, DELETE, DETACH, REMOVE, or DROP.
3. Use parameterized queries where possible ($ticker, $name, etc.).
4. LIMIT results to at most 25 rows.
5. Return human-readable column aliases.
6. For multi-hop queries, traverse relationships step by step.
7. Use OPTIONAL MATCH for relationships that might not exist.

## Examples

Query: "Who are Nvidia's competitors?"
Cypher: MATCH (c:Company {ticker: 'NVDA'})-[:COMPETES_WITH]->(comp:Company) RETURN comp.name AS competitor, comp.ticker AS ticker, comp.sector AS sector LIMIT 10

Query: "Which companies supply to Apple?"
Cypher: MATCH (s:Company)-[:SUPPLIES_TO]->(c:Company {ticker: 'AAPL'}) RETURN s.name AS supplier, s.ticker AS ticker LIMIT 10

Query: "Which of Nvidia's suppliers were mentioned in their customers' earnings calls?"
Cypher: MATCH (nvda:Company {ticker: 'NVDA'})<-[:SUPPLIES_TO]-(supplier:Company), (nvda)<-[:CUSTOMER_OF]-(customer:Company)-[:HAS_EARNINGS]->(ec:EarningsCall), (supplier)-[m:MENTIONED_IN]->(ec) RETURN supplier.name AS supplier, customer.name AS customer, ec.quarter AS quarter, m.sentiment AS sentiment LIMIT 25

Query: "Who is the CEO of Tesla?"
Cypher: MATCH (p:Person)-[:EXEC_OF]->(c:Company {ticker: 'TSLA'}) WHERE p.title CONTAINS 'CEO' RETURN p.name AS name, p.title AS title LIMIT 5

Set requires_graph=false for queries like "What is Apple's stock price?" — those don't need graph traversal.
"""

# ── Blocklist for write operations ─────────────────────────────────────────

_WRITE_PATTERN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|CALL\s+\{)\b",
    re.IGNORECASE,
)

_CYPHER_TIMEOUT = 8.0


class CypherGenerator:
    """Generate read-only Cypher queries from natural language.

    Usage::

        gen = CypherGenerator()
        result = await gen.generate("Who are Nvidia's competitors?")
        if result and result.requires_graph:
            records = await graph_client.execute(result.cypher)
    """

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        self._llm = llm or get_chat_model(settings.gpt_4o_mini, temperature=0.0)
        self._generator = self._llm.with_structured_output(CypherQuery)

    @timed("cypher_generator.generate", warn_threshold_s=3.0)
    async def generate(
        self,
        query: str,
        *,
        ticker_hint: str | None = None,
    ) -> CypherQuery | None:
        """Generate a Cypher query for a natural-language question.

        Args:
            query: User's natural-language question.
            ticker_hint: Optional ticker to help resolve ambiguous company names.

        Returns:
            CypherQuery with cypher, explanation, and requires_graph flag.
            None if generation fails or the query doesn't need graph traversal.
        """
        context = ""
        if ticker_hint:
            context = f"\n\nNote: The user is currently discussing {ticker_hint}."

        try:
            result: CypherQuery = await asyncio.wait_for(
                self._generator.ainvoke([
                    SystemMessage(content=_CYPHER_SYSTEM_PROMPT),
                    HumanMessage(content=f"Generate a Cypher query for: {query[:500]}{context}"),
                ]),
                timeout=_CYPHER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[CYPHER_GEN] Generation timed out for: %.80s", query)
            return None
        except Exception as exc:
            logger.error("[CYPHER_GEN] Generation failed: %s", exc)
            return None

        # Safety check: reject any write operations.
        if _WRITE_PATTERN.search(result.cypher):
            logger.error(
                "[CYPHER_GEN] BLOCKED write operation in generated Cypher: %s",
                result.cypher[:200],
            )
            return None

        logger.info(
            "[CYPHER_GEN] Generated | requires_graph=%s | Cypher: %.100s",
            result.requires_graph, result.cypher,
        )
        return result
