# Finsight Application Workflows

This document outlines key sequence and data workflows in the Finsight system using Mermaid diagrams.

---

## 1. Portfolio Stress-Testing Workflow
Illustrates the user flow when submitting a custom portfolio for historical crisis evaluation.

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
    PS-->>API: Return stress results JSON
    API-->>UI: Response (crises returns & drawdown %)
    UI-->>User: Render results cards & custom SVG chart
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
