"""Neo4j graph database client — connection management and Cypher execution.

Thread-safe async wrapper around the neo4j Python driver.
Connection is lazy-initialized on first use and pooled for the app lifetime.

Configuration via environment variables:
    NEO4J_URI       — bolt://localhost:7687 (default)
    NEO4J_USER      — neo4j (default)
    NEO4J_PASSWORD   — required in production
    NEO4J_DATABASE   — neo4j (default)
"""

import asyncio
import os
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy import — neo4j driver is optional; the system degrades gracefully.
try:
    from neo4j import AsyncDriver, AsyncGraphDatabase  # type: ignore[import-untyped]
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None  # type: ignore[assignment, misc]
    AsyncDriver = None  # type: ignore[assignment, misc]


class GraphClient:
    """Async Neo4j client with lazy connection pooling.

    Usage::

        client = GraphClient()
        records = await client.execute("MATCH (c:Company) RETURN c.name LIMIT 5")
        await client.close()
    """

    def __init__(self) -> None:
        self._driver: Any | None = None
        self._uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._user = os.getenv("NEO4J_USER", "neo4j")
        self._password = os.getenv("NEO4J_PASSWORD", "")
        self._database = os.getenv("NEO4J_DATABASE", "neo4j")

    @property
    def available(self) -> bool:
        """Return True if the neo4j driver is installed."""
        return _NEO4J_AVAILABLE

    async def _ensure_driver(self) -> Any:
        """Lazily create the async driver."""
        if not _NEO4J_AVAILABLE:
            raise RuntimeError(
                "neo4j Python driver is not installed. "
                "Run: pip install neo4j"
            )
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=10,
            )
            logger.info("[GRAPH] Connected to Neo4j at %s", self._uri)
        return self._driver

    async def execute(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        *,
        timeout: float = 15.0,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as list of dicts.

        Args:
            cypher: Cypher query string.
            parameters: Optional query parameters.
            timeout: Query timeout in seconds.

        Returns:
            List of record dicts. Empty list on error.
        """
        driver = await self._ensure_driver()

        try:
            async with driver.session(database=self._database) as session:
                result = await asyncio.wait_for(
                    session.run(cypher, parameters or {}),
                    timeout=timeout,
                )
                records = [dict(record) async for record in result]
                logger.info(
                    "[GRAPH] Executed query | Records: %d | Query: %.80s",
                    len(records), cypher,
                )
                return records

        except TimeoutError:
            logger.warning("[GRAPH] Query timed out after %.1fs: %.80s", timeout, cypher)
            return []
        except Exception as exc:
            logger.error("[GRAPH] Query failed: %s | Query: %.80s", exc, cypher)
            return []

    async def execute_write(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Execute a write transaction (CREATE, MERGE, SET, DELETE)."""
        driver = await self._ensure_driver()

        async with driver.session(database=self._database) as session:

            async def _tx(tx):
                await tx.run(cypher, parameters or {})

            await session.execute_write(_tx)
            logger.debug("[GRAPH] Write executed: %.80s", cypher)

    async def close(self) -> None:
        """Close the driver and release all connections."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("[GRAPH] Neo4j connection closed")

    async def health_check(self) -> bool:
        """Return True if Neo4j is reachable."""
        if not _NEO4J_AVAILABLE:
            logger.info("[GRAPH] neo4j driver not installed — graph features disabled")
            return False
        try:
            driver = await self._ensure_driver()
            async with driver.session(database=self._database) as session:
                result = await session.run("RETURN 1 AS ok")
                record = await result.single()
                return record is not None and record["ok"] == 1
        except Exception as exc:
            logger.warning("[GRAPH] Health check failed: %s", exc)
            return False
