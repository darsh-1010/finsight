# Finsight API Reference Guide

This document lists the primary REST API endpoints available on the Finsight Backend.

---

## 1. Authentication

### Signup User
- **Method**: `POST`
- **Path**: `/api/v1/auth/signup`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123",
    "tier_level": 1
  }
  ```
  Note: `role_id` is not (and cannot be) client-supplied — every signup is assigned the standard
  user role server-side, regardless of request body content.
- **Response**:
  ```json
  {
    "message": "User registered successfully",
    "user_id": 42
  }
  ```

### Login User
- **Method**: `POST`
- **Path**: `/api/v1/auth/login`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123"
  }
  ```
- **Response**: Sets authorization HTTP-only cookie and returns user status.

---

## 2. Onboarding

### Submit Onboarding Answers
- **Method**: `POST`
- **Path**: `/api/v1/onboarding/answers`
- **Request Body**:
  ```json
  [
    {
      "question_id": 1,
      "option_id": 3,
      "answer_value": "Intermediate"
    }
  ]
  ```
- **Response**: Status confirmation.

---

## 3. Market Insights

### Trigger Watchlist Scan
- **Method**: `POST`
- **Path**: `/api/v1/market_insights/scan`
- **Request Body**:
  ```json
  {
    "user_id": "usr_101",
    "user_tier": 3,
    "tickers": ["AAPL", "TSLA"]
  }
  ```
- **Response**:
  ```json
  {
    "scanned": 2,
    "events_detected": 1,
    "insights": [
      {
        "category": "Price Action",
        "topic": "Volume Spike",
        "confidence": 0.85,
        "summary": "Apple trading volume spiked 40% above average."
      }
    ]
  }
  ```

---

## 4. Portfolio Sandbox

### Run Portfolio Stress Test
- **Method**: `POST`
- **Path**: `/api/v1/portfolio/stress-test`
- **Headers**: Requires valid User Session cookie.
- **Request Body**:
  ```json
  {
    "portfolio": [
      {
        "ticker": "AAPL",
        "weight": 0.6
      },
      {
        "ticker": "MSFT",
        "weight": 0.4
      }
    ]
  }
  ```
- **Response**:
  ```json
  {
    "crises": {
      "2008_Crash": {
        "return_pct": -42.85,
        "max_drawdown": -48.20,
        "status": "success"
      },
      "2020_COVID": {
        "return_pct": -21.40,
        "max_drawdown": -25.10,
        "status": "success"
      }
    },
    "concentration": {
      "hhi": 0.745,
      "risk_level": "concentrated",
      "max_position": { "ticker": "AAPL", "weight": 0.85 },
      "flagged_positions": [
        { "ticker": "AAPL", "weight": 0.85 },
        { "ticker": "MSFT", "weight": 0.15 }
      ],
      "sector_breakdown": { "Technology": 1.0 },
      "flagged_sectors": [{ "sector": "Technology", "weight": 1.0 }]
    }
  }
  ```
  `concentration` is always present alongside `crises`: `risk_level` is one of
  `diversified` / `moderate` / `concentrated` (HHI bands `<0.15` / `0.15–0.25` / `>0.25`);
  `flagged_positions` lists any single ticker above 10% of the portfolio; `flagged_sectors`
  lists any sector above 20%. Sector data comes from live Yahoo Finance data per ticker, with
  a small static sector map (`TECH`, `REITS`, `ENERGY`, ...) as a fallback if that lookup
  fails — verified locally against a real 429 rate-limit from Yahoo, which degraded cleanly to
  the fallback map instead of failing the request.

---

## 5. Research

### Get a Cited Research Report
- **Method**: `POST`
- **Path**: `/api/v1/research/report`
- **Headers**: Requires valid User Session cookie. Gated to Growth tier (2) and above.
- **Request Body**:
  ```json
  { "query": "AAPL" }
  ```
- **Response**: `ResearchReportResponse` — ticker, company name, an LLM-synthesized
  summary/valuation/growth/risk take, filing highlights, and a `sources` list citing the
  yFinance data and the SEC 10-K filing excerpt used.

---

## 6. Chat

### Send a Chat Message
- **Method**: `POST`
- **Path**: `/api/v1/chat` (proxied to the ml service)
- No response schema change, but the assistant's answer may now include one or two extra
  guidance notes ("risk nudges") appended before the model generates its reply, computed from
  the same ticker data already fetched for the turn — no extra latency or LLM call:
  - A **reactive-decision nudge** when the message reads as a buy/sell decision right after a
    >5% single-day move on the resolved ticker.
  - A **hype-pattern flag** when the resolved ticker is an illiquid microcap (market cap under
    $300M) with an abnormal volume spike (>2x average) and no P/E data on file — the signature
    of a pump-and-dump pattern.
