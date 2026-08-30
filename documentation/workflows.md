# Finsight Application Workflows

This document outlines key sequence and data workflows in the Finsight system using Mermaid diagrams.

---

## 1. Portfolio Stress-Testing Workflow
Illustrates the user flow when submitting a custom portfolio for historical crisis evaluation.
Since 2026-08-30, the same request also returns a concentration-risk score (see §4).

```mermaid
sequenceDiagram
    autonumber
    actor User as Investor / Student
    participant UI as React Sandbox UI
    participant API as FastAPI Backend
    participant PS as PortfolioService
    participant YF as Yahoo Finance API

    User->>UI: Input Tickers & Weights (e.g. 60% AAPL, 40% MSFT)
    UI->>UI: Check weights sum to 100% (normalize if needed)
    User->>UI: Click "Run Simulation"
    UI->>API: POST /api/v1/portfolio/stress-test
    API->>PS: calculate_stress_test(portfolio)
    PS->>YF: Fetch historical Close prices for periods (2008 & 2020)
    YF-->>PS: Return daily Close price DataFrame
    PS->>PS: Calculate daily returns & maximum peak-to-trough drawdown
    API->>PS: calculate_concentration(portfolio)
    PS->>YF: Fetch live sector per ticker (falls back to static map on error)
    PS->>PS: Compute HHI, flag positions >10% and sectors >20%
    PS-->>API: Return stress results + concentration JSON
    API-->>UI: Response (crises returns & drawdown %, concentration score)
    UI-->>User: Render results cards, SVG chart, and concentration badge
```

---

## 2. Weekly Email Briefings Delivery Workflow
Illustrates the background cron workflow delivering weekly briefings to Tier 4 subscribed users.

```mermaid
sequenceDiagram
    autonumber
    participant Cron as CronService Loop
    participant DB as SQLite Database
    participant PS as PortfolioService
    participant SES as Amazon SES Service
    actor User as Active Investor

    Cron->>Cron: Scheduled Weekly Tick (Saturday 06:00 IST)
    Cron->>DB: Query active users & watchlists
    Cron->>PS: get_7_day_performance(watchlist_tickers)
    PS-->>Cron: Returns prices & percent changes
    Cron->>Cron: Render Jinja HTML email template
    Cron->>SES: Send rendered HTML email
    SES->>User: Deliver "Your Weekly Finsight Briefing"
```

---

## 3. Real-Time Market Scanner Workflow
Illustrates how the market trigger scanner syncs live events and runs fallbacks.

```mermaid
sequenceDiagram
    autonumber
    participant API as Scanner API Route
    participant RAG as RAG Retrieval Client
    participant LLM as LLM Engine
    participant Tav as Tavily API (Search Fallback)

    API->>API: Watchlist Triggered
    API->>RAG: Get Recent Context (Vector Search)
    RAG-->>API: Return text chunks
    API->>LLM: classify_event(event, context)
    alt Confidence >= 55%
        LLM-->>API: Returns Structured Category & Topic
    else Confidence < 55% (Context Insufficient)
        API->>Tav: Query live financial web search
        Tav-->>API: Return search web snippets
        API->>LLM: classify_event(event, context + search snippets)
        LLM-->>API: Returns Structured Category & Topic
    end
```

---

## 4. Ask FinSight Risk-Nudge Workflow
Illustrates how a reactive-decision or pump-and-dump warning gets appended to the chat prompt,
using ticker data the pipeline was already going to fetch for the turn — no extra LLM call.

```mermaid
sequenceDiagram
    autonumber
    actor User as Investor
    participant Chat as ChatService
    participant QS as QueryService
    participant YF as Yahoo Finance API
    participant Nudge as _build_risk_nudges()
    participant LLM as Chat LLM

    User->>Chat: "Should I sell AAPL right now?"
    Chat->>QS: analyze_and_fetch(message)
    QS->>YF: Resolve ticker & fetch FinancialContext
    YF-->>QS: price_change_pct, market_cap, volume, avg_volume, pe_ratio
    QS-->>Chat: analysis_result (contexts, expansion)
    Chat->>Nudge: _build_risk_nudges(message, analysis_result)
    alt Reactive language + >5% move on resolved ticker
        Nudge-->>Chat: Reactive-decision nudge
    end
    alt Microcap + volume spike (>2x avg) + no P/E data
        Nudge-->>Chat: Pump-and-dump hype-pattern nudge
    end
    Chat->>LLM: messages + [Query Analysis] + risk nudges (as SystemMessages)
    LLM-->>Chat: Factual answer, informed by the nudge context
    Chat-->>User: Response
```
