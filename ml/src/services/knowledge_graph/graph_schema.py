"""Knowledge Graph schema — defines nodes, edges, and constraint setup.

Node types:
    Company     — ticker, name, sector, industry, market_cap
    Person      — name, title (CEO, CFO, etc.)
    Sector      — name (Technology, Healthcare, etc.)
    Filing      — type (10-K, 10-Q, 8-K), date, accession_number
    EarningsCall— date, quarter, fiscal_year

Edge types:
    COMPETES_WITH   — Company → Company
    SUPPLIES_TO     — Company → Company
    CUSTOMER_OF     — Company → Company
    SUBSIDIARY_OF   — Company → Company
    EXEC_OF         — Person → Company
    BELONGS_TO      — Company → Sector
    HAS_FILING      — Company → Filing
    HAS_EARNINGS    — Company → EarningsCall
    MENTIONED_IN    — Company → Filing | EarningsCall  (with sentiment property)
"""

from src.services.knowledge_graph.graph_client import GraphClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Constraint & index setup (idempotent) ──────────────────────────────────

_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX IF NOT EXISTS FOR (f:Filing) ON (f.accession_number)",
    "CREATE INDEX IF NOT EXISTS FOR (e:EarningsCall) ON (e.ticker, e.quarter)",
]


async def ensure_schema(client: GraphClient) -> None:
    """Create constraints and indexes if they don't exist.

    Safe to call on every startup — all statements are IF NOT EXISTS.
    """
    for stmt in _CONSTRAINTS + _INDEXES:
        try:
            await client.execute_write(stmt)
        except Exception as exc:
            # Log but don't crash — schema might already exist.
            logger.warning("[GRAPH_SCHEMA] Statement skipped: %s | %s", stmt[:60], exc)

    logger.info("[GRAPH_SCHEMA] Schema ensured (%d constraints, %d indexes)",
                len(_CONSTRAINTS), len(_INDEXES))


# ── Seed data helpers ──────────────────────────────────────────────────────

async def seed_company(
    client: GraphClient,
    ticker: str,
    name: str,
    sector: str = "",
    industry: str = "",
    **extra,
) -> None:
    """Create or update a Company node and its Sector relationship."""
    cypher = """
    MERGE (c:Company {ticker: $ticker})
    SET c.name = $name,
        c.sector = $sector,
        c.industry = $industry,
        c.updated_at = datetime()
    """
    for key in extra:
        cypher += f", c.{key} = ${key}\n"

    params = {"ticker": ticker.upper(), "name": name, "sector": sector, "industry": industry}
    params.update(extra)
    await client.execute_write(cypher, params)

    # Link to Sector node if provided.
    if sector:
        await client.execute_write(
            """
            MERGE (s:Sector {name: $sector})
            WITH s
            MATCH (c:Company {ticker: $ticker})
            MERGE (c)-[:BELONGS_TO]->(s)
            """,
            {"sector": sector, "ticker": ticker.upper()},
        )


async def seed_relationship(
    client: GraphClient,
    from_ticker: str,
    to_ticker: str,
    rel_type: str,
    **properties,
) -> None:
    """Create a relationship between two companies.

    Args:
        from_ticker: Source company ticker.
        to_ticker: Target company ticker.
        rel_type: One of COMPETES_WITH, SUPPLIES_TO, CUSTOMER_OF, SUBSIDIARY_OF.
        **properties: Additional edge properties (e.g. since="2020").
    """
    valid_types = {"COMPETES_WITH", "SUPPLIES_TO", "CUSTOMER_OF", "SUBSIDIARY_OF"}
    if rel_type not in valid_types:
        logger.warning("[GRAPH_SCHEMA] Invalid relationship type: %s", rel_type)
        return

    cypher = f"""
    MATCH (a:Company {{ticker: $from_ticker}})
    MATCH (b:Company {{ticker: $to_ticker}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r += $props
    """
    await client.execute_write(
        cypher,
        {"from_ticker": from_ticker.upper(), "to_ticker": to_ticker.upper(), "props": properties},
    )


async def seed_executive(
    client: GraphClient,
    name: str,
    title: str,
    company_ticker: str,
) -> None:
    """Create a Person node linked to a Company via EXEC_OF."""
    await client.execute_write(
        """
        MERGE (p:Person {name: $name})
        SET p.title = $title, p.updated_at = datetime()
        WITH p
        MATCH (c:Company {ticker: $ticker})
        MERGE (p)-[:EXEC_OF]->(c)
        """,
        {"name": name, "title": title, "ticker": company_ticker.upper()},
    )
