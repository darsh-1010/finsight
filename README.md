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
├── Dockerfile.frontend     ← FE image (Next.js standalone production build)
├── nginx.conf              ← Nginx config for the web proxy
│
├── backend/                ← FastAPI Backend (auth, DB, chat proxy)
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
└── frontend/               ← Next.js + React + Tailwind + TypeScript frontend (Purple/Black theme)
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
| **Frontend** | http://localhost | Next.js Server (Docker standalone) |
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

---

## 📈 New Features

### 1. Portfolio Stress-Testing Sandbox
- Access via the **Portfolio Sandbox** tab in the sidebar.
- Enter custom stock tickers and weights, check allocation metrics, and evaluate drawdown performance during historical market crises:
  - **2008 Financial Crisis**
  - **2020 COVID-19 Crash**
- Custom premium SVG bar-chart comparison.

### 2. Weekly Email Briefings
- Automated weekly performance digests delivered directly to your inbox.
- Configure/opt-out of briefings in **User Profile > Security & Preferences > Weekly Email Briefings**. Note that this premium service is entitlement-locked and requires **Tier 4 (Institutional)**.

---

## 📄 Detailed Documentation

For deep dives and installation guides:
- [Installation Guide](file:///c:/Users/10102/Downloads/codebase/finsight/documentation/install.md) — Local manual setup.
- [Architecture Blueprint](file:///c:/Users/10102/Downloads/codebase/finsight/documentation/architecture.md) — System flow details.
- [API Reference Guide](file:///c:/Users/10102/Downloads/codebase/finsight/documentation/api.md) — Full backend endpoint docs.
- [Workflows & Diagrams](file:///c:/Users/10102/Downloads/codebase/finsight/documentation/workflows.md) — Mermaid workflows.

