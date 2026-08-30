# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Claude Code

- **Enforcement vs. guidance**: `AGENTS.md` above is context, not a hard gate — Claude tries to follow
  it but can drift on vague or conflicting instructions. Don't just assert compliance with §2/§9 (e.g.
  "ruff clean") — actually run `ruff check` / `pylint --rcfile=...` and show the result before calling
  a change done.
- **Planning**: use plan mode for anything matching §1's "non-trivial change" bar instead of writing
  the plan straight into chat. Track §0's atomic sub-tasks with the todo list tool rather than a
  hand-maintained `task.md`.
- **Research**: use `WebSearch`/`WebFetch` for §1's research step.
- **Skills**: if a skill in the current skill list already covers the task (lint review, PDF/xlsx/docx
  work, etc.), use it instead of re-deriving the same steps inline.
- **graphify**: only follow the graphify section if those tools are actually present in this session —
  don't invent a `graphify` shell invocation that isn't installed.
- **Reuse before writing**: before adding a function, component, constant, or type, search for an
  existing equivalent (`graphify query "<question>"`, then `grep`/`Glob`) and reuse or extend it
  instead of writing a parallel implementation — cheaper in tokens and in future bugs than a
  duplicate. Only write new code when nothing close already exists.
- **Modular, reusable code**: one function/component does one job (AGENTS.md §3); factor shared
  logic into a helper instead of copy-pasting it at two call sites. Watch for the specific failure
  mode of a duplicate top-level `class`/`def` silently shadowing the original (ruff `F811`) — this
  repo has had that bug twice (a duplicate `class PortfolioService` and a duplicate `downgrade()`
  in an Alembic migration); `ruff check --select F401,F811,F841` catches it and plain unused
  imports/variables in one pass.

Keep this file and `AGENTS.md` each under ~200 lines — both load in full every session regardless of
the `@import` split, so trim content rather than relocating it.

## Architecture

Three independently-deployed services in one monorepo, wired together over HTTP (see
[documentation/architecture.md](documentation/architecture.md) for the full diagram):

- **`backend/`** — FastAPI (Python 3.12). Owns auth/sessions, the SQLAlchemy DB (SQLite locally,
  Postgres in prod, via [backend/app/core/database.py](backend/app/core/database.py)), tier/entitlement
  checks, portfolio sandbox, and WebSocket chat relay. Routers live in `backend/app/api/routes/` and
  are wired in [backend/app/main.py](backend/app/main.py); each one delegates to a same-named service
  in `backend/app/services/`. Migrations are Alembic (`backend/alembic/`).
- **`ml/`** — FastAPI (Python 3.11). Owns the LLM chat/RAG pipeline, Weaviate vector search, structured
  insight extraction, and the broker/news scrapers (`ml/src/data_sources/`, one class per source —
  BofA, Deutsche Bank, Investing.com, etc. — run on a schedule by `scraper_scheduler.py` /
  `ScraperJobQueue`). Entry point is [ml/src/api/main.py](ml/src/api/main.py).
- **`frontend/`** — Next.js App Router + React + Tailwind v4 + Redux Toolkit. Views in
  `frontend/src/views/`, API clients in `frontend/src/api/` (axios), store slices in
  `frontend/src/store/`.

**Cross-service calls**: `backend` → `ml` over HTTP using `ML_API_URL` / `ML_SERVER_SECRET_TOKEN`
(shared-secret auth, not a user JWT); `ml` → `backend` the same way via `BACKEND_API_URL` for syncing
scraped insights (`ml_data_transfer.py` on both sides). `frontend` only ever talks to `backend`
(`VITE_API_BASE_URL`/`NEXT_PUBLIC_*` — some env var names are legacy from a pre-Next.js Vite frontend,
see `.env.example`); `backend` proxies chat/RAG requests to `ml` and relays responses over its own
WebSocket to the client. Shared infra: Redis (session/cache TTLs), Weaviate (vectors, `ml` only), S3
(uploads/reports), SES (weekly email briefings).

**Tiers**: 4 subscription tiers (Starter → Enterprise), all free (Stripe was removed — see
`CHANGELOG.md`). Tier gates live in `backend/app/services/` (entitlement/tier resolver) and mirror into
`ml`'s per-tier quotas/model selection (`ML_TIER_*_*` env vars).

## Commands

```bash
# Run a single service locally (see .claude/launch.json for the frontend dev server)
cd backend && uvicorn app.main:app --reload --port 8001
cd ml && uvicorn src.api.main:app --reload --port 8002
cd frontend && npm run dev

# Or everything via Docker (see README.md Quick Start for .env setup / seeding)
docker compose up -d --build
docker compose exec backend alembic upgrade head

# Lint (the enforced gate — see AGENTS.md §2 for the pylint hard limits)
make lint                                                   # all three services
cd backend && ruff check .                                  # or: cd ml && ruff check .
cd frontend && npm run lint
pylint <file> --rcfile=backend/.pylintrc                    # stricter supplementary bar (backend)
pylint <file> --rcfile=ml/.pylintrc                         # same, for ml/
cd backend && ruff format .                                 # or: make format (all services)

# Tests
make test                                                   # backend + ml, no coverage gate
make test-backend / make test-ml                            # with --cov-fail-under=60
cd backend && pytest tests/test_auth.py::test_login -v      # single backend test
cd ml && pytest tests/services/test_chat_guardrails.py -v   # single ml test
cd frontend && npx vitest run path/to/file.test.tsx         # single frontend test (no test files yet)

# Security / full local CI
make security                                                # bandit SAST, backend + ml
make ci                                                       # lint -> security -> test-all
```

## graphify

`graphify-out/GRAPH_REPORT.md` exists and is current (built from HEAD) — read it before a broad
codebase sweep; it lists community hubs, "god nodes" (`cn()`, `get_logger()`, `ChatService`, `User`,
`useAuth()`, ...), and per-community file groupings.

```bash
graphify query "<question>"      # find relevant files/functions before a broad grep
graphify explain "<concept>"
graphify path "A" "B"            # trace data flow between two components
graphify update .                # refresh the graph after edits (AST-only, no API cost)
```

A `PostToolUse` hook in `.claude/settings.local.json` already runs `graphify update .` automatically
after `Edit`/`Write`/`NotebookEdit` — you generally don't need to invoke `update` by hand.
`graphify-out/` is generated/gitignored; never commit it.
