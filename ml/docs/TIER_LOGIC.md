# Tier-Wise Logic Implementation

This document outlines how user tiers and feature entitlements are handled across the FinSight RAG system.

## 1. Tier Resolution (How the system decides your tier)
The system uses a "Trust but Verify" approach with a multi-stage fallback mechanism to resolve a user's tier features:

1.  **Request Override**: Checks if a tier is explicitly forced by the internal system for a specific request.
2.  **Redis Cache**: Looks up the user's tier in a fast Redis cache (expires every few hours).
3.  **Backend API**: Fetches the latest tier definition from the master database if the cache is empty.
4.  **Static Fallback**: If everything else fails, it defaults to the hardcoded **Tier 1 (Free)** settings.

---

## 2. Feature Comparison Table

| Feature | Tier 0 (Guest Preview) | Tier 1 (Free) | Tier 2 (Basic) | Tier 3 (Pro) | Tier 4 (Institutional) | Tier 5 (Enterprise) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Used** | ENV: `TIER_0_MODEL` | ENV: `TIER_1_MODEL` | ENV: `TIER_2_MODEL` | ENV: `TIER_3_MODEL` | ENV: `TIER_4_MODEL` | ENV: `TIER_5_MODEL` |
| **Direct LLM Only** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Web Access** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Prompt Profile** | Guest | Concise | Standard | Synthesis | Professional | Professional |
| **Search Depth** | 0 (No search) | 3 sources | 10 sources | 20 sources | 50 sources |
| **Max Tokens** | 512 | 1,024 | 2,048 | 4,096 | 8,192 |
| **Web Access** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Reasoning Trace** | ❌ | ❌ | ✅ (Visible) | ✅ (Visible) | ✅ (Visible) |
| **Document Uploads**| ❌ | ❌ | ✅ | ✅ | ✅ |
| **Quant/Risk Tools**| ❌ | ❌ | ❌ | ✅ | ✅ |
| **Prompt Profile** | Concise | Standard | Synthesis | Professional | Professional |

---

## 3. Explaining the Key Features

### Search Depth
Determines how many information chunks are pulled from the vector database. Higher tiers get more context, leading to more accurate and detailed answers.

### Max Tokens
The hard limit on how long the AI's response can be. Institutional users get significantly longer and more detailed reports.

### Reasoning Trace
When enabled (Tier 3+), the AI shows its "thought process" (e.g., *Retrieving context... Analysing tickers...*) before giving the final answer.

### Quant Access
Exclusive to Tier 4. This injects real-time risk metrics and volatility data into the chat context for specific stock tickers.

### Prompt Profiles
Tiers use different system prompts. Tier 1 is optimized for speed/conciseness, while Tier 4 is optimized for professional financial analysis.

---

## 4. Quota Enforcement
Limits are enforced via a middleware layer that tracks daily requests stored in Redis:

- **Tracking**: Every request increments a counter in Redis keyed by `user_id` and `date`.
- **Enforcement**: If the count exceeds the tier's daily limit, the API returns a `429 Too Many Requests` status.
- **Fail-Open**: If Redis is down, the system allows the request to pass to ensure service availability.

---

## 5. Other Tiered Systems
- **PDF Extraction**: The `PDFScraper` uses a "Tiered Extraction" approach unrelated to user levels. It attempts PyPDF2 (fastest) → pdfplumber (better accuracy) → OCR (scanned documents) in order to maximize text retrieval from difficult files.
