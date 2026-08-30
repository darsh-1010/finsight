# Changelog

## [2026-08-30]

### Added
- **Concentration-risk badge** on the Portfolio Sandbox: every stress-test run now also scores
  the submitted portfolio's concentration risk via a new `PortfolioService.calculate_concentration`
  — a Herfindahl-Hirschman Index (HHI) summary, any single position above 10%, and any sector
  above 20% (real Yahoo Finance sector data, falling back to the existing hardcoded sector map
  on lookup failure). Returned as a new `concentration` field on `POST /portfolio/stress-test`,
  ungated for all tiers. Backed by real-world research: practitioner guidance flags any single
  position >10% and any sector >20-25% as concentration risk.
- **Ask FinSight risk nudges**: two evidence-backed heuristics computed from ticker data already
  fetched for the turn, appended as guidance to the LLM prompt (`_build_risk_nudges` in
  `chat_service.py`) — no new LLM call or data fetch:
  - A **reactive-decision nudge** when a buy/sell question follows a >5% single-day move on the
    resolved ticker, noting that moves this size often partially revert and encouraging the user
    to weigh their original thesis rather than the day's move. Retail investors lose an
    estimated $1,600/year on average to emotionally-driven trades (FinanceBuzz, 2026 survey).
  - A **pump-and-dump hype-pattern flag** for a resolved ticker matching illiquid microcap
    (<$300M market cap) + abnormal volume spike (>2x average) + no P/E data on file — the
    signature the FBI reports a +300% rise in complaints about in 2025.

### Fixed / Verified
- Live-tested both features against a real local stack (real SQLite DB, real Redis, real
  yfinance network calls, no mocks): the concentration badge correctly rendered `concentrated`
  for an 85/15 AAPL/MSFT split (HHI 0.745) and `diversified` for a 10-position equal-weight
  portfolio (HHI 0.10), end-to-end through the actual frontend UI.
- The live run surfaced a real Yahoo Finance 429 rate-limit on the sector lookup — confirmed
  `_resolve_sector`'s exception handling (`json.JSONDecodeError` is a `ValueError` subclass)
  degrades cleanly to the static sector map instead of failing the request, exactly as designed.
- The panic-decision nudge was verified against a real, cross-checked market event: Advance
  Auto Parts' actual -24.55% single-day move on 2026-08-20 (computed from yfinance's own
  historical OHLC, matching press coverage of "-25.2%") correctly triggers the nudge only on a
  reactive message ("should I sell...") and stays silent on a calm informational question about
  the same stock.
- The pump-and-dump flag was verified against a real, currently-trending microcap (Ucommune
  International, market cap ~$7.3M, no P/E on file): correctly silent against its real live
  snapshot (no active volume spike at test time) and correctly fires once a volume spike is
  present, confirming the heuristic is conservative rather than trigger-happy.

## [2026-08-27] (2)

### Added
- Adopted `litellm` (previously an unused dependency since the repo's first commit) as the
  FreeLLMAPI-primary/OpenAI-fallback engine for the parts of `ml/` where it's safely
  compatible: `ml/src/llm/litellm_router.py` is a new shared `litellm.Router` factory
  (one primary+fallback deployment pair per model name actually in use) plus a
  `.beta.chat.completions.parse`-compatible shim so existing structured-output callers
  needed zero code changes.
  - `market_insights/llm_engine.py`, `research/report_compiler.py`: full swap off
    `FallbackAsyncOpenAI` (they only ever used `.beta.chat.completions.parse`).
  - `market_insights/daily_compiler.py`, `weekly_compiler.py`: only their structured-output
    call swapped; their separate OpenAI Responses API + `web_search_preview` call is
    unchanged (litellm doesn't cover that surface).
  - `query_service.py`, `ticker_service.py`, `rag/retrieval_grader.py`,
    `knowledge_graph/cypher_generator.py`: these had *no* fallback behaviour at all before
    (plain `ChatOpenAI`) — they now get FreeLLMAPI+OpenAI resilience via `get_chat_model()`
    (`ChatLiteLLMRouter`) for the first time.
  - `weaviate/embeddings.py`: `FallbackOpenAIEmbeddings`'s hand-rolled try/except replaced
    with the shared Router's `embedding`/`aembedding`, same public interface.
  - **Deliberately left untouched**: the OpenAI Responses API + hosted web-search tool, the
    OpenAI Files API (document uploads), and the main chat's `.with_fallbacks()+.bind_tools()`
    LangChain chain — litellm doesn't cleanly cover these, and there are no real API keys in
    this environment to verify a riskier swap against a live provider.
  - New dependency `langchain-litellm>=0.7.0`; bumped `litellm`'s floor to `>=1.98.0`
    (the version actually tested) from the previously-unused `>=1.30.0`.

## [2026-08-27]

### Added
- **Research** feature (Phase 1): a dedicated `/research` page where a user enters a
  ticker or company name and gets a structured, cited research brief combining live
  yFinance fundamentals with the company's latest SEC 10-K filing excerpt, synthesized
  via OpenAI structured outputs. Gated to Growth tier (2) and above.
  - `ml`: new `ResearchReportCompiler` service (`ml/src/services/research/`), cached in
    Redis per-ticker (6h TTL), reusing `YFinanceDataSource`, `EdgarSource`, and
    `ResponsePostprocessor`'s anti-hallucination checks. New `POST /api/v1/research/report`
    route, now covered by `QuotaMiddleware`.
  - `backend`: new `POST /api/v1/research/report` proxy that resolves the caller's real
    subscription tier server-side (never trusts a client-supplied tier) before forwarding
    to the ml service.
  - `frontend`: new Research page/view, sidebar entry, and a locked-feature upsell for
    users below Growth tier (first real use of the previously-unwired `LockedFeature`
    component).

### Fixed
- `YFinanceDataSource.fetch()` now catches `KeyError` (in addition to the existing
  `ValueError`/`TypeError`/`AttributeError`/`RuntimeError`) and normalizes it into
  `YFinanceError`. Delisted/invalid tickers made yfinance's lazy `fast_info` property
  raise a bare `KeyError` (e.g. missing `currentTradingPeriod`) that escaped uncaught,
  surfacing as a raw 500 instead of a clean "ticker not found" response — affects every
  caller of `fetch()`, not just Research. Found via a live-network integration test.
- The backend's research-report proxy no longer double-encodes the ml service's JSON
  error body inside its own `detail` field (was rendering as a literal
  `{"detail":"..."}` string in the UI); it now unwraps the inner `detail` first.
- **Security**: public signup no longer trusts a client-supplied `role_id` — it always
  assigns the standard user role server-side. Previously any `POST /api/v1/auth/signup`
  request could pass `role_id: 2` and be created as an admin, since that's the only role
  id the app's own seed data ever uses for the admin role. `role_id` has been removed
  from the signup request entirely (frontend and backend).
- **Reliability**: `create_access_token`/`create_refresh_token` now include a unique
  `jti` claim. JWTs only carry second-resolution `exp`, so two tokens issued for the same
  user within the same second (e.g. signup immediately followed by login) were
  byte-identical and violated `user_sessions.token_hash`'s unique constraint, crashing
  with a 500. This was causing widespread flaky test failures across the backend suite;
  fixing it took a full run from ~40 flaky errors to 120/120 passing consistently.
- `TickerService.resolve()` now catches `redis.exceptions.RedisError` on both its cache
  read and write (it wasn't a subclass of any exception already caught), so a brief Redis
  outage during company-name ticker resolution degrades to the LLM-resolution fallback
  instead of crashing with a 500 — affects chat, market insights, and Research alike.

## [2026-08-24]

### Changed
- FinSight is now completely free. Removed Stripe entirely: the `stripe` SDK dependency,
  `StripeService`, all `stripe_*` fields on the `Tier` model/schema, and the Stripe-billing
  UI copy on the Pricing page, Upgrade modal, and Billing profile tab.
- `POST /api/v1/payments/create-checkout-session` (mock Stripe checkout) replaced with
  `POST /api/v1/payments/select-tier`, which switches a user's tier immediately at no cost
  via the existing `TierService.change_tier`.
- Signing up with a tier selected (`?tier=N`) now applies that tier immediately instead of
  leaving the account on Foundation pending a checkout that never completed.

### Removed
- Payment Success / Payment Cancel pages and views (no longer needed — tier switching is
  synchronous, not a redirect-based checkout).
- Monthly/yearly billing period toggle and all `price_amount`/`price_id` fields from the
  tiers API, frontend tier interfaces, and fallback tier data.
- Dead Stripe customer-portal code path (`createPortalSession`/`handleManageSubscription`)
  that had no UI trigger.
- Dead "redirecting to payment gateway" spinner on the email verification screen.

### Fixed
- Admin tier price edits no longer make a live call to the Stripe API with a fake product
  ID (previously would 400 in production).
- Selecting a paid tier at signup now actually takes effect (previously silently stayed on
  Foundation forever, since nothing ever consumed the `pending_tier_id` it set).
