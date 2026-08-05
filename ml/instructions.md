# FinSight ML — Setup Instructions

## Prerequisites

- Docker & Docker Compose
- Python 3.10+
- An OpenAI API key (set in `.env`)

## 1. Install Dependencies

```bash
cd ml
pip install -r requirements.txt
```

## 2. Start Services

```bash
docker-compose up -d
```

This starts Weaviate, Redis, and Neo4j. Neo4j default password is `finsight2026` — override via `NEO4J_PASSWORD` in your `.env`.

## 3. Seed the Knowledge Graph

Populates Neo4j with company nodes, sector relationships, executive data (from yFinance), and curated competitive/supply-chain edges.

```bash
python -m src.scripts.seed_knowledge_graph
```

To seed specific tickers only:

```bash
python -m src.scripts.seed_knowledge_graph --tickers AAPL MSFT NVDA GOOGL
```

Default tickers: NVDA, AMD, INTC, TSM, ASML, AAPL, MSFT, GOOGL, AMZN, META.

## 4. Ingest SEC EDGAR Filings

Downloads 10-K and 10-Q filings from SEC EDGAR, chunks them with structure-aware splitting (respects section boundaries like Item 1, Risk Factors, MD&A), and stores them in Weaviate.

```bash
python -m src.scripts.edgar_ingestion --tickers AAPL MSFT --types 10-K 10-Q
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--tickers` | *(required)* | Space-separated list of stock tickers |
| `--types` | `10-K 10-Q` | Filing types to fetch |
| `--limit` | `3` | Max filings per ticker per type |

No API key needed — SEC EDGAR is free and public.

## Notes

- All three new features (Knowledge Graph, EDGAR ingestion, Retrieval Grader) degrade gracefully. If Neo4j is down, graph queries are skipped. If the grader times out, chunks are assumed relevant. The chatbot works fine without any of these running.
- The Retrieval Grader uses your existing OpenAI key (gpt-4.1-mini) — no extra setup.
