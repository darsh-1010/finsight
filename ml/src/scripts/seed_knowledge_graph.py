"""Seed the knowledge graph with initial company data and relationships.

Populates Company nodes, Sector nodes, executive relationships, and
competitive/supply-chain edges for a starter set of tickers.

Uses yFinance for live company metadata (sector, industry, market cap)
so the graph stays grounded in real data.

Usage::

    python -m src.scripts.seed_knowledge_graph
    python -m src.scripts.seed_knowledge_graph --tickers AAPL MSFT GOOGL
"""

import argparse
import asyncio
from typing import Any

import yfinance as yf

from src.services.knowledge_graph.graph_client import GraphClient
from src.services.knowledge_graph.graph_schema import (
    ensure_schema,
    seed_company,
    seed_executive,
    seed_relationship,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Default semiconductor sector tickers (from the build plan) ─────────────

DEFAULT_TICKERS = ["NVDA", "AMD", "INTC", "TSM", "ASML", "AAPL", "MSFT", "GOOGL", "AMZN", "META"]

# ── Known relationships (curated seed data) ────────────────────────────────
# These are well-known public relationships. The graph construction pipeline
# can later augment these via LLM extraction from filings.

_RELATIONSHIPS = [
    # Semiconductor competition
    ("NVDA", "AMD", "COMPETES_WITH"),
    ("NVDA", "INTC", "COMPETES_WITH"),
    ("AMD", "INTC", "COMPETES_WITH"),
    # Supply chain
    ("TSM", "NVDA", "SUPPLIES_TO"),
    ("TSM", "AMD", "SUPPLIES_TO"),
    ("TSM", "AAPL", "SUPPLIES_TO"),
    ("ASML", "TSM", "SUPPLIES_TO"),
    ("ASML", "INTC", "SUPPLIES_TO"),
    # Cloud/tech competition
    ("MSFT", "GOOGL", "COMPETES_WITH"),
    ("MSFT", "AMZN", "COMPETES_WITH"),
    ("GOOGL", "AMZN", "COMPETES_WITH"),
    ("GOOGL", "META", "COMPETES_WITH"),
    # Customer relationships
    ("NVDA", "MSFT", "SUPPLIES_TO"),
    ("NVDA", "GOOGL", "SUPPLIES_TO"),
    ("NVDA", "AMZN", "SUPPLIES_TO"),
    ("NVDA", "META", "SUPPLIES_TO"),
]


async def _fetch_company_info(ticker: str) -> dict[str, Any]:
    """Fetch company metadata from yFinance."""
    try:
        stock = yf.Ticker(ticker)
        info = await asyncio.to_thread(lambda: stock.info)
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap", 0),
            "country": info.get("country", ""),
            "exchange": info.get("exchange", ""),
        }
    except Exception as exc:
        logger.warning("[SEED] Failed to fetch info for %s: %s", ticker, exc)
        return {"name": ticker, "sector": "", "industry": ""}


async def seed_graph(tickers: list[str] | None = None) -> dict[str, int]:
    """Seed the knowledge graph with company data and relationships.

    Args:
        tickers: List of tickers to seed (defaults to DEFAULT_TICKERS).

    Returns:
        Stats dict with counts of nodes and relationships created.
    """
    tickers = tickers or DEFAULT_TICKERS
    client = GraphClient()

    logger.info("[SEED] Starting knowledge graph seeding | tickers=%s", tickers)

    stats = {"companies": 0, "relationships": 0, "errors": 0}

    try:
        # Ensure schema constraints and indexes exist.
        await ensure_schema(client)

        # Seed Company nodes with live data.
        for ticker in tickers:
            try:
                info = await _fetch_company_info(ticker)
                await seed_company(
                    client,
                    ticker=ticker,
                    name=info["name"],
                    sector=info.get("sector", ""),
                    industry=info.get("industry", ""),
                    market_cap=info.get("market_cap", 0),
                    country=info.get("country", ""),
                    exchange=info.get("exchange", ""),
                )
                stats["companies"] += 1
                logger.info("[SEED] Seeded company: %s (%s)", ticker, info["name"])
            except Exception as exc:
                logger.error("[SEED] Failed to seed %s: %s", ticker, exc)
                stats["errors"] += 1

        # Seed relationships.
        active_tickers = set(t.upper() for t in tickers)
        for from_t, to_t, rel_type in _RELATIONSHIPS:
            if from_t in active_tickers and to_t in active_tickers:
                try:
                    await seed_relationship(client, from_t, to_t, rel_type)
                    stats["relationships"] += 1
                except Exception as exc:
                    logger.error(
                        "[SEED] Failed to create %s->%s (%s): %s",
                        from_t, to_t, rel_type, exc,
                    )
                    stats["errors"] += 1

    finally:
        await client.close()

    logger.info("[SEED] Complete: %s", stats)
    return stats


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Seed the financial knowledge graph")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help=f"Ticker symbols to seed (default: {' '.join(DEFAULT_TICKERS)})",
    )
    args = parser.parse_args()

    result = asyncio.run(seed_graph(args.tickers))
    print(f"\nSeeding complete: {result}")


if __name__ == "__main__":
    from src.scripts.path_bootstrap import bootstrap
    bootstrap()
    main()
