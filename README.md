# FinSight Monorepo

> **FinSight** – AI-powered Financial Concierge & Investment Intelligence Platform

A production-ready monorepo combining the **Backend (BE)**, **ML/RAG Service (ML)**, and **React Frontend (FE)** for the FinSight platform.

---

## 🏗️ Repository Structure

```
finsight/
├── .env                    ← Unified environment file (single source of truth)
├── .env.example            ← Template — copy to .env and fill in values
├── docker-compose.yml      ← Single compose file for all services
├── Dockerfile.backend      ← BE image (FastAPI, Python 3.12)
├── Dockerfile.ml           ← ML image (FastAPI, Python 3.11, Playwright, Camoufox)
├── Dockerfile.frontend     ← FE image (Vite build → Nginx serve)
├── nginx.conf              ← Nginx config for the React SPA
│
├── backend/                ← FastAPI Backend (auth, DB, Stripe, chat proxy)
│   ├── app/
│   ├── alembic/
│   ├── requirements.txt
│   └── ...
│
├── ml/                     ← FastAPI ML/RAG service (OpenAI/FreeLLMAPI, Weaviate, scrapers)
│   ├── src/
│   ├── config/
│   ├── requirements.txt
│   └── ...
│
└── frontend/               ← React + Vite + TypeScript frontend (Violet/Lavender theme)
    ├── src/
    ├── package.json
    └── ...
```

---

## ⚙️ AI Engine (FreeLLMAPI)
The platform is powered by **FreeLLMAPI** as its primary LLM backend provider, with an automatic transparent fallback to standard **OpenAI** to guarantee continuous uptime and reliable query responses.

---

## 💳 Pricing Tiers
FinSight features a consolidated **4-tier** subscription architecture:
1. **Starter** (Level 1) — Foundational tools & explaining mode.
2. **Growth** (Level 2) — Risk-thinking frameworks & concept Q&A.
3. **Premium** (Level 3) — Interactive intelligence & scenario analysis.
4. **Enterprise** (Level 4) — Full signals-aware quant features & priority compute.

*Note: The old Level 5 (Elite / Advisory) has been completely removed.*

---

## 🚀 Quick Start (Docker — Recommended)

### 1. Set up environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys and credentials
```

### 2. Start all services

```bash
docker compose up -d --build
```

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Seed initial data (Local Development)

```bash
# Seed Tiers Catalog
docker compose exec backend python -m app.seeds.seed_tiers

# Seed Local Test Accounts (starter@, growth@, premium@, enterprise@, admin@)
docker compose exec backend python -m app.seeds.seed_local_test_users

# Seed Token Refill and Cap Rules
docker compose exec backend python -m app.seeds.seed_tier_token_configs
```

---

## 🌐 Service URLs

| Service | URL | Description |
|---|---|---|
| **Frontend** | http://localhost:5173 | React SPA (Vite Local Dev) |
| **Backend API** | http://localhost:8001 | FastAPI BE |
| **Backend Docs** | http://localhost:8001/docs | Swagger UI |
| **ML API** | http://localhost:8002 | FastAPI ML (mapped port) |
| **ML Docs** | http://localhost:8002/docs | Swagger UI |
| **Weaviate** | http://localhost:8080 | Vector DB |
| **Redis** | localhost:6380 | Cache (mapped port) |

---

## 🧪 Running Tests

```bash
# Backend tests
pytest tests/ -v --tb=short

# ML tests
pytest ml/tests/ -v
```
