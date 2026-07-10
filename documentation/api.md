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
    "role_id": 1,
    "tier_level": 1
  }
  ```
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
    }
  }
  ```
