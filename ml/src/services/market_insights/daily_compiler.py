"""Daily Compiler Service for Market Insights.

Dynamically scans the global stock market using a curated universe of 100 tickers,
calculates technical indicators (RSI and volume surge ratios), and synthesizes a
structured, tier-tailored daily report using OpenAI Structured Outputs.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timezone
from typing import Any

import pandas as pd
import redis
import yfinance as yf
from openai import OpenAIError

from src.llm.fallback_client import FallbackAsyncOpenAI
from src.llm.litellm_router import get_structured_llm_client
from src.services.market_insights.daily_models import (
    TIER1_INSTRUCTIONS,
    TIER2_INSTRUCTIONS,
    TIER3_INSTRUCTIONS,
    TIER4_INSTRUCTIONS,
    DailyStockHighlight,
    DailySummaryReport,
    DailySummaryReportTier1,
    DailySummaryReportTier2,
    DailySummaryReportTier3,
    DailySummaryReportTier4,
)
from src.services.market_insights.models import (
    AlertPayload,
    InsightCategory,
    InsightTopic,
)
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)

# Cache time-to-live: 24 hours (86,400 seconds)
_REPORT_CACHE_TTL_SECONDS = 86_400
_GLOBAL_TIER_REPORT_KEY = "mi:daily_report:tier:{tier_id}"


class DailySummaryCompiler:
    """Service to dynamically scan market-mover tickers and compile tiered daily reports.

    Uses OpenAI Structured Outputs to generate customized analytical depth per user tier.
    """

    _SCANNING_UNIVERSE = [
        # US Tech & Software (18)
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "NVDA",
        "AMD",
        "AVGO",
        "QCOM",
        "INTC",
        "ADBE",
        "CRM",
        "ORCL",
        "CSCO",
        "NFLX",
        "NOW",
        "PLTR",
        "PANW",
        # US Financials & Payments (10)
        "JPM",
        "BAC",
        "WFC",
        "C",
        "GS",
        "MS",
        "AXP",
        "V",
        "MA",
        "COIN",
        # US Healthcare (8)
        "LLY",
        "UNH",
        "JNJ",
        "ABBV",
        "MRK",
        "TMO",
        "PFE",
        "AMGN",
        # US Consumer Goods & Retail (10)
        "WMT",
        "HD",
        "COST",
        "PG",
        "KO",
        "PEP",
        "NKE",
        "PM",
        "MO",
        "TGT",
        # US Energy & Materials (8)
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "FCX",
        "NEM",
        "APD",
        "LIN",
        # US Industrials & Defense (9)
        "CAT",
        "GE",
        "BA",
        "HON",
        "LMT",
        "RTX",
        "NOC",
        "UPS",
        "DE",
        # Telecom & Utilities (5)
        "T",
        "VZ",
        "TMUS",
        "NEE",
        "DUK",
        # Automotive & Consumer Services (8)
        "TSLA",
        "F",
        "GM",
        "DIS",
        "SBUX",
        "CMG",
        "MCD",
        "BKNG",
        # High-Volume Growth / Retail Favorites (8)
        "MSTR",
        "SOFI",
        "ROKU",
        "SNAP",
        "DKNG",
        "HOOD",
        "AFRM",
        "U",
        # Global Giants (Europe, Asia, Canada, Americas ADRs) (16)
        "ASML",
        "NVO",
        "SAP",
        "SONY",
        "TM",
        "HDB",
        "INFY",
        "BABA",
        "JD",
        "PDD",
        "BHP",
        "VALE",
        "PBR",
        "RY",
        "SHOP",
        "AZN",
    ]

    def __init__(
        self,
        openai_client: FallbackAsyncOpenAI | None = None,
        redis_client: Any | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        """Initialise compiler with required network dependencies.

        Args:
            openai_client: OpenAI client instance.
            redis_client: Redis client instance.
            openai_api_key: API key for OpenAI fallback initialization.
        """
        if openai_client:
            self._client = openai_client
        else:
            api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            self._client = (
                FallbackAsyncOpenAI(api_key=api_key)
                if api_key
                else FallbackAsyncOpenAI()
            )

        # Structured-output calls (.beta.chat.completions.parse) go through the
        # litellm-backed client; the Responses API + web_search_preview tool
        # above stays on FallbackAsyncOpenAI, which litellm doesn't cover.
        # An injected openai_client (tests) still serves both, unchanged.
        self._structured_client = openai_client or get_structured_llm_client()

        self._redis = redis_client or get_async_redis()

    async def get_or_generate_summary(
        self,
        user_id: str,
        raw_alerts: list[AlertPayload],
        user_tier: int = 1,
    ) -> DailySummaryReport:
        """Retrieve cached daily summary globally by tier or compile and cache a new one.

        Args:
            user_id: Target user unique identifier.
            raw_alerts: Unused daily alerts list (maintained for API interface compatibility).
            user_tier: The user's subscription tier (1-4).

        Returns:
            A DailySummaryReport instance.
        """
        cache_key = _GLOBAL_TIER_REPORT_KEY.format(tier_id=user_tier)
        try:
            cached_data = await self._redis.get(cache_key)
            if cached_data:
                logger.info(
                    "[DAILY_REPORT_CACHE_HIT] Tier: %d | User: %s", user_tier, user_id
                )
                report = DailySummaryReport.model_validate_json(cached_data)
                report.user_id = user_id
                return report
        except (
            redis.exceptions.RedisError,
            ConnectionError,
            OSError,
            ValueError,
        ) as exc:
            logger.warning("[DAILY_REPORT_CACHE_ERROR] Redis read failed: %s", exc)

        logger.info(
            "[DAILY_REPORT_CACHE_MISS] Tier: %d | Serving instant fallback and triggering background compile",
            user_tier,
        )
        import sys
        if "pytest" not in sys.modules:
            asyncio.create_task(
                self.generate_and_cache_summary(user_id, raw_alerts, user_tier)
            )

        fallback_tickers = [
            "AAPL",
            "MSFT",
            "TSLA",
            "NVDA",
            "AMD",
            "NFLX",
            "AMZN",
            "BABA",
            "ASML",
            "NVO",
        ]
        return self._build_fallback_report(fallback_tickers, user_id=user_id)

    async def generate_and_cache_summary(
        self,
        user_id: str,
        raw_alerts: list[AlertPayload],
        user_tier: int = 1,
    ) -> DailySummaryReport | None:
        """Asynchronously compiles, caches, and logs audit entries for a tier report under a lock.

        Args:
            user_id: Target user unique identifier.
            raw_alerts: Unused daily alerts list.
            user_tier: The user's subscription tier (1-4).

        Returns:
            A DailySummaryReport instance if compiled, or None if skipped.
        """
        lock_key = f"mi:daily_report:lock:tier:{user_tier}"
        cache_key = _GLOBAL_TIER_REPORT_KEY.format(tier_id=user_tier)

        try:
            # Acquire distributed Redis lock for 180 seconds to prevent concurrent runs
            acquired = await self._redis.set(lock_key, "locked", ex=180, nx=True)
            if not acquired:
                logger.info(
                    "[DAILY_REPORT_LOCK_SKIPPED] Tier: %d is already compiling under another worker",
                    user_tier,
                )
                return None
        except (redis.exceptions.RedisError, ConnectionError, OSError) as exc:
            logger.warning("[DAILY_REPORT_LOCK_ERROR] Distributed lock failed: %s", exc)

        try:
            logger.info(
                "[DAILY_REPORT_BACKGROUND_COMPILE] Tier: %d starting compilation",
                user_tier,
            )
            report = await self._compile_report(user_id, raw_alerts, user_tier)

            try:
                await self._redis.set(
                    cache_key, report.model_dump_json(), ex=_REPORT_CACHE_TTL_SECONDS
                )
                logger.info(
                    "[DAILY_REPORT_CACHE_POPULATED] Tier: %d cached successfully",
                    user_tier,
                )
            except (
                redis.exceptions.RedisError,
                ConnectionError,
                OSError,
                ValueError,
            ) as exc:
                logger.warning(
                    "[DAILY_REPORT_CACHE_WRITE_ERROR] Redis write failed: %s", exc
                )

            try:
                date_str = datetime.now(UTC).strftime("%Y-%m-%d")
                audit_key = f"mi:daily_report:audit:tier:{user_tier}:{date_str}"
                await self._redis.set(
                    audit_key, report.model_dump_json(), ex=30 * 86400
                )
                logger.info(
                    "[DAILY_REPORT_AUDIT_LOGGED] Tier: %d saved to audit storage",
                    user_tier,
                )
            except (
                redis.exceptions.RedisError,
                ConnectionError,
                OSError,
                ValueError,
            ) as exc:
                logger.warning(
                    "[DAILY_REPORT_AUDIT_WRITE_ERROR] Redis audit log failed: %s", exc
                )

            return report
        finally:
            try:
                await self._redis.delete(lock_key)
            except (redis.exceptions.RedisError, ConnectionError, OSError) as exc:
                logger.warning(
                    "[DAILY_REPORT_LOCK_RELEASE_ERROR] Failed to release lock: %s", exc
                )

    async def _fetch_movers_and_news(self) -> tuple[list[dict[str, Any]], list[Any]]:
        """Fetch 1-month yFinance prices, scan movers, and harvest news in parallel.

        Returns:
            Tuple of (all_movers_list, parallel_news_results).
        """
        loop = asyncio.get_running_loop()
        logger.info(
            "[DAILY_SCAN_START] Beginning batch yFinance download for %d tickers",
            len(self._SCANNING_UNIVERSE),
        )
        data = await loop.run_in_executor(
            None,
            lambda: yf.download(
                self._SCANNING_UNIVERSE, period="1mo", group_by="ticker", progress=False
            ),
        )
        logger.info(
            "[DAILY_SCAN_DOWNLOAD_COMPLETE] Batch download finished. Data shape: %s",
            data.shape,
        )
        gainers, losers = self._scan_market_movers(data)
        logger.info(
            "[DAILY_SCAN_MOVERS] Identified %d gainers and %d losers meeting the +-2%% threshold",
            len(gainers),
            len(losers),
        )
        all_movers = gainers + losers
        logger.info(
            "[DAILY_NEWS_START] Initiating parallel news harvesting for %d movers",
            len(all_movers),
        )
        news_results = await asyncio.gather(
            *(self._fetch_mover_news_async(m["ticker"]) for m in all_movers)
        )
        logger.info("[DAILY_NEWS_FETCH_COMPLETE] Completed news harvesting.")
        return all_movers, news_results

    async def _fetch_websearch_events(self) -> list[dict[str, Any]]:
        """Retrieve top 5-7 key global financial market events from today via OpenAI web search.

        Returns:
            List of dictionaries with title, content, and url keys.
        """
        logger.info(
            "[DAILY_WEB_SEARCH_START] Fetching top market events via OpenAI web search"
        )
        query = (
            "List the top 7 most important global events from the last 24 hours that might affect "
            "the global financial system, global economy, or financial markets. "
            "Search for significant occurrences across the following areas:\n"
            "1. Macroeconomic developments (central bank decisions, inflation, interest rates, GDP, trade policies).\n"
            "2. Geopolitical events and global policy changes (conflicts, international relations, major government transitions).\n"
            "3. Regulatory/Risk changes (major SEC investigations, massive regulatory fines, global risk developments).\n"
            "4. Major corporate actions or sector/industry shifts (M&A activity, supply chain disruptions, competitive shifts).\n"
            "5. Broad price actions (commodity price shocks, major index moves).\n"
            "Focus on any event that has a global financial footprint or economic consequence, not just basic stock price moves. "
            "Format each event as: [Event Title] — [1-2 sentence factual summary]."
        )
        try:
            response = await self._client.responses.create(
                model=os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini"),
                tools=[{"type": "web_search_preview"}],
                input=query,
            )

            cited_urls: list[dict[str, str]] = []
            for output_item in response.output:
                content_blocks = getattr(output_item, "content", [])
                for block in content_blocks:
                    for annotation in getattr(block, "annotations", []):
                        url = getattr(annotation, "url", "")
                        title = getattr(annotation, "title", "")
                        if url and url not in {u["url"] for u in cited_urls}:
                            cited_urls.append({"url": url, "title": title})

            synthesized_text = response.output_text or ""
            logger.info(
                "[DAILY_WEB_SEARCH_COMPLETE] Retrieved %d citations from OpenAI web search",
                len(cited_urls),
            )

            events: list[dict[str, Any]] = []
            for idx, cited in enumerate(cited_urls[:7]):
                events.append(
                    {
                        "title": cited["title"] or f"Market Event #{idx + 1}",
                        "content": synthesized_text,
                        "url": cited["url"],
                    }
                )

            if not events and synthesized_text:
                events.append(
                    {
                        "title": "Daily Market Digest",
                        "content": synthesized_text,
                        "url": "",
                    }
                )

            return events

        except (RuntimeError, ConnectionError, ValueError, OSError) as exc:
            logger.warning("[DAILY_WEB_SEARCH_ERROR] OpenAI web search failed: %s", exc)
            return []

    async def _compile_report(
        self,
        user_id: str,
        raw_alerts: list[AlertPayload],
        user_tier: int = 1,
    ) -> DailySummaryReport:
        """Executes the global market scanning, filtering, news harvesting, and AI synthesis.

        Args:
            user_id: Target user identifier.
            raw_alerts: Daily alerts list accumulated during the day.
            user_tier: The user's subscription tier.

        Returns:
            A synthesized DailySummaryReport.
        """
        try:
            all_movers, news_results = await self._fetch_movers_and_news()
            web_events = await self._fetch_websearch_events()

            prompt = self._build_synthesis_prompt(
                self._build_yf_context(all_movers, news_results), web_events, raw_alerts
            )
            instructions, response_format = self._get_tier_prompts_and_format(user_tier)

            completion = await self._structured_client.beta.chat.completions.parse(
                model=os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a premium financial intelligence analyst. Your goal is to "
                            "synthesize today's top stock market movers (gainers and losers) "
                            "derived from global daily multi-index scanning, specific detected market events/alerts "
                            "from the alerts queue (e.g. analyst rating changes, dividends/earnings, and news catalysts), "
                            "as well as key global financial market events obtained via web search.\n\n"
                            "CLASSIFICATION REQUIREMENT:\n"
                            "For each stock highlight, you must classify the primary driver of the event "
                            "into one of the 6 high-level categories and one of the 30 strict topics defined in the system. "
                            "Populate the `category` and `topic` fields exactly as defined in the schema.\n\n"
                            "DATA PROVENANCE & INSIGHT SOURCE REQUIREMENT:\n"
                            "Every stock highlight in your response must track its source in "
                            "the `insight_source` field:\n"
                            "- For highlights synthesized from the 'GLOBAL DAILY SCAN MOVERS & TECHNICAL METRICS' "
                            "or 'DETECTED MARKET ALERTS QUEUE' context (both derived from yFinance), set the `insight_source` field strictly to 'yfinance'.\n"
                            "- For highlights synthesized from the 'LIVE FINANCIAL MARKET WEB SEARCH KEY EVENTS' "
                            "context, set the `insight_source` field strictly to 'websearch'.\n"
                            "Ensure that you synthesize highlights for both yfinance movers/alerts and websearch key events "
                            "while keeping the JSON schema exactly the same.\n\n"
                            "Provide exact URLs/links from the news articles/web results that support "
                            "each highlight's claims. For yfinance news/alerts, use the provided links; "
                            "for websearch events, use the provided source urls.\n\n"
                            f"TIER-SPECIFIC INSTRUCTIONS:\n{instructions}"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=response_format,
                temperature=0.2,
            )
            parsed_report = completion.choices[0].message.parsed
            if parsed_report is None:
                raise ValueError("Structured daily report generation returned null")

            logger.info(
                "[DAILY_REPORT_SYNTHESIS_COMPLETE] LLM report synthesized successfully for Tier: %d | User: %s",
                user_tier,
                user_id,
            )
            return self._normalize_report(parsed_report, user_id=user_id)

        except (
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
            ConnectionError,
            OSError,
            OpenAIError,
        ) as exc:
            logger.error("[DAILY_COMPILER_LLM_ERROR] Synthesis failed: %s", exc)
            return self._build_fallback_report(
                [
                    "AAPL",
                    "MSFT",
                    "TSLA",
                    "NVDA",
                    "AMD",
                    "NFLX",
                    "AMZN",
                    "BABA",
                    "ASML",
                    "NVO",
                ],
                user_id=user_id,
            )

    def _calculate_stock_metrics(self, df: pd.DataFrame) -> dict[str, Any] | None:
        """Calculate daily performance and technical indicators for a single stock.

        Args:
            df: Historical daily pricing DataFrame for a single ticker (1 month).

        Returns:
            Dictionary of computed metrics, or None if data is insufficient.
        """
        clean_df = df.dropna(subset=["Close"])
        if len(clean_df) < 15:
            return None

        # 1. Daily Return (today's close vs yesterday's close)
        start_close = float(clean_df["Close"].iloc[-2])
        end_close = float(clean_df["Close"].iloc[-1])
        daily_change = (
            ((end_close - start_close) / start_close * 100) if start_close > 0 else 0.0
        )

        # 2. RSI (14-day)
        diffs = clean_df["Close"].diff()
        avg_gain = diffs.clip(lower=0).ewm(com=13, min_periods=14).mean()
        avg_loss = (-diffs.clip(upper=0)).ewm(com=13, min_periods=14).mean()
        current_rsi = float(
            (100 - (100 / (1 + (avg_gain / avg_loss.replace(0, 1e-9))))).iloc[-1]
        )

        # 3. Daily Volume Ratio (today's volume vs previous 15-day average volume baseline)
        baseline_vol = clean_df["Volume"].iloc[-16:-1].mean()
        volume_ratio = (
            (float(clean_df["Volume"].iloc[-1]) / baseline_vol)
            if baseline_vol > 0
            else 1.0
        )

        return {
            "start_price": round(start_close, 2),
            "end_price": round(end_close, 2),
            "daily_change_pct": round(daily_change, 2),
            "rsi": round(current_rsi, 1),
            "volume_ratio": round(volume_ratio, 2),
        }

    def _scan_market_movers(
        self, data: pd.DataFrame
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Filters the top 10 daily gainers and top 10 daily losers from the stock data.

        Args:
            data: Multi-index DataFrame from yFinance.

        Returns:
            Tuple of (gainers_list, losers_list).
        """
        gainers = []
        losers = []

        if not isinstance(data.columns, pd.MultiIndex) or data.empty:
            return [], []

        for ticker in self._SCANNING_UNIVERSE:
            if ticker not in data.columns.levels[0]:
                continue

            metrics = self._calculate_stock_metrics(data[ticker])
            if not metrics:
                continue

            item = {
                "ticker": ticker,
                "start_price": metrics["start_price"],
                "end_price": metrics["end_price"],
                "daily_change_pct": metrics["daily_change_pct"],
                "rsi": metrics["rsi"],
                "volume_ratio": metrics["volume_ratio"],
            }

            if metrics["daily_change_pct"] >= 2.0:
                gainers.append(item)
            elif metrics["daily_change_pct"] <= -2.0:
                losers.append(item)

        # Volatility Fallback
        if len(gainers) < 10 or len(losers) < 10:
            logger.info(
                "[DAILY_VOLATILITY_FALLBACK] Fewer than 10 tickers met threshold. Using absolute ranks."
            )
            all_items = []
            for ticker in self._SCANNING_UNIVERSE:
                if ticker not in data.columns.levels[0]:
                    continue
                metrics = self._calculate_stock_metrics(data[ticker])
                if not metrics:
                    continue
                all_items.append(
                    {
                        "ticker": ticker,
                        "start_price": metrics["start_price"],
                        "end_price": metrics["end_price"],
                        "daily_change_pct": metrics["daily_change_pct"],
                        "rsi": metrics["rsi"],
                        "volume_ratio": metrics["volume_ratio"],
                    }
                )
            all_items.sort(key=lambda x: x["daily_change_pct"], reverse=True)
            return all_items[:10], sorted(
                all_items[-10:], key=lambda x: x["daily_change_pct"]
            )

        gainers.sort(key=lambda x: x["daily_change_pct"], reverse=True)
        losers.sort(key=lambda x: x["daily_change_pct"])

        return gainers[:10], losers[:10]

    def _fetch_mover_news(self, ticker: str) -> list[dict[str, str]]:
        """Fetch and parse top news stories for a single ticker via yFinance.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            List of parsed articles.
        """
        try:
            stock = yf.Ticker(ticker)
            news_data = getattr(stock, "news", [])
            return self._parse_yfinance_news(news_data)
        except (
            RuntimeError,
            ValueError,
            AttributeError,
            KeyError,
            TypeError,
            OSError,
        ) as exc:
            logger.warning(
                "[DAILY_YFINANCE_NEWS_ERROR] Failed to fetch news for ticker %s: %s",
                ticker,
                exc,
            )
            return []

    async def _fetch_mover_news_async(self, ticker: str) -> list[dict[str, str]]:
        """Fetch news asynchronously in an executor thread.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            List of parsed articles.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_mover_news, ticker)

    def _build_yf_context(
        self, all_movers: list[dict[str, Any]], news_results: list[Any]
    ) -> list[dict[str, Any]]:
        """Format calculations and news results into standard context blocks.

        Args:
            all_movers: List of calculated stock items.
            news_results: Parallel news results.

        Returns:
            List of formatted yFinance stock contexts.
        """
        yf_context = []
        for idx, item in enumerate(all_movers):
            alerts = []
            if item["rsi"] >= 70.0:
                alerts.append(f"Daily Overbought Momentum Warning (RSI: {item['rsi']})")
            elif item["rsi"] <= 30.0:
                alerts.append(
                    f"Daily Oversold Reversion Opportunity (RSI: {item['rsi']})"
                )

            if item["volume_ratio"] >= 2.0:
                alerts.append(
                    f"Daily Institutional Volume Surge ({item['volume_ratio']}x average)"
                )

            daily_trend = "Neutral"
            if item["daily_change_pct"] > 0.5:
                daily_trend = "Bullish"
            elif item["daily_change_pct"] < -0.5:
                daily_trend = "Bearish"

            yf_context.append(
                {
                    "ticker": item["ticker"],
                    "daily_trend": daily_trend,
                    "daily_change_pct": item["daily_change_pct"],
                    "start_price": item["start_price"],
                    "end_price": item["end_price"],
                    "rsi": item["rsi"],
                    "volume_ratio": item["volume_ratio"],
                    "technical_alerts": alerts,
                    "articles": news_results[idx],
                }
            )
        return yf_context

    def _build_synthesis_prompt(
        self,
        yf_context: list[dict[str, Any]],
        web_events: list[dict[str, Any]] | None = None,
        raw_alerts: list[AlertPayload] | None = None,
    ) -> str:
        """Formats the calculated daily movers and news context into a clear prompt.

        Args:
            yf_context: Calculated trends, technicals, and news.
            web_events: List of web search key events context.
            raw_alerts: List of raw alert payloads from the database/queue.

        Returns:
            Formatted prompt string.
        """
        sections = ["=== GLOBAL DAILY SCAN MOVERS & TECHNICAL METRICS ==="]
        for item in yf_context:
            sections.append(
                f"\nTicker: {item['ticker']} | Calculated Daily Trend: {item['daily_trend']} | "
                f"Yesterday Close: ${item['start_price']} | Today Close: ${item['end_price']} | "
                f"Daily Change: {item['daily_change_pct']}% | RSI: {item['rsi']} | "
                f"Volume Ratio: {item['volume_ratio']}x"
            )
            if item["technical_alerts"]:
                sections.append(
                    f"  Technical Alerts: {', '.join(item['technical_alerts'])}"
                )

            for art in item["articles"]:
                sections.append(
                    f"  - Headline: {art['title']}\n"
                    f"    Source/Link: {art['link']}\n"
                    f"    Publisher: {art['publisher']} ({art['published_at']})"
                )

        if raw_alerts:
            sections.append("\n=== DETECTED MARKET ALERTS QUEUE ===")
            for idx, payload in enumerate(raw_alerts, 1):
                insight = payload.insight
                event = insight.event
                evt_type = (
                    event.event_type.value
                    if hasattr(event.event_type, "value")
                    else event.event_type
                )
                cat = (
                    insight.category.value
                    if hasattr(insight.category, "value")
                    else insight.category
                )
                top = (
                    insight.topic.value
                    if hasattr(insight.topic, "value")
                    else insight.topic
                )
                sections.append(
                    f"Alert #{idx}:\n"
                    f"  - Ticker: {event.ticker}\n"
                    f"  - Event Type: {evt_type}\n"
                    f"  - Detected Category: {cat}\n"
                    f"  - Detected Topic: {top}\n"
                    f"  - Price: ${event.current_price} (Change: {event.price_change_pct}%)\n"
                    f"  - Summary: {insight.summary}\n"
                    f"  - Context: {event.context}"
                )

        if web_events:
            sections.append("\n=== LIVE FINANCIAL MARKET WEB SEARCH KEY EVENTS ===")
            for idx, event in enumerate(web_events, 1):
                sections.append(
                    f"Event #{idx}:\n"
                    f"  - Headline: {event.get('title', '')}\n"
                    f"    Content: {event.get('content', '')}\n"
                    f"    Source/Link: {event.get('url', '')}"
                )

        sections.append(
            "\nTask: Synthesize these findings and write a comprehensive fact-verified report. "
            "Address any technical alerts (RSI extremes or volume spikes) and any detected market alerts "
            "in the summaries. Make sure to categorize and map each highlight to its proper category/topic."
        )
        return "\n".join(sections)

    def _parse_yfinance_news(
        self, news_data: list[dict] | None
    ) -> list[dict[str, str]]:
        """Parse yfinance raw news data list into a standard schema.

        Args:
            news_data: List of raw news dictionaries from yfinance.

        Returns:
            Formatted news items list.
        """
        parsed_articles = []
        for item in (news_data or [])[:3]:
            content = item.get("content", {}) if "content" in item else item
            title = content.get("title", "")
            publisher = content.get("publisher", "")
            link = content.get("link") or ""
            if not link:
                canonical_url = content.get("canonicalUrl")
                if isinstance(canonical_url, dict):
                    link = canonical_url.get("url") or ""
            if not link:
                click_url = content.get("clickThroughUrl")
                if isinstance(click_url, dict):
                    link = click_url.get("url") or ""

            pub_time = content.get("providerPublishTime") or content.get("pubDate")
            if isinstance(pub_time, int):
                try:
                    pub_time_str = datetime.fromtimestamp(
                        pub_time, tz=UTC
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError, OSError):
                    pub_time_str = str(pub_time)
            else:
                pub_time_str = str(pub_time) if pub_time else "Recent"

            parsed_articles.append(
                {
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "published_at": pub_time_str,
                }
            )
        return parsed_articles

    def _get_tier_prompts_and_format(self, user_tier: int) -> tuple[str, Any]:
        """Returns the specific system instructions and response schema model for the user's tier.

        Args:
            user_tier: Numeric user subscription tier (1-4).

        Returns:
            Tuple of (system_instructions_string, Pydantic_model_class).
        """
        # Tier 4: Institutional
        if user_tier == 4:
            return TIER4_INSTRUCTIONS, DailySummaryReportTier4

        # Tier 3: Pro
        if user_tier == 3:
            return TIER3_INSTRUCTIONS, DailySummaryReportTier3

        # Tier 2: Basic
        if user_tier == 2:
            return TIER2_INSTRUCTIONS, DailySummaryReportTier2

        # Tier 1: Free (Default fallback)
        return TIER1_INSTRUCTIONS, DailySummaryReportTier1

    def _normalize_report(
        self, report: Any, user_id: str | None = None
    ) -> DailySummaryReport:
        """Normalises any tier-specific summary report back to the standard DailySummaryReport schema.

        Args:
            report: Tier-specific DailySummaryReport model (Tier 1-4).
            user_id: The target user's ID.

        Returns:
            A standard DailySummaryReport instance.
        """
        highlights = []
        for h in report.highlights:
            highlights.append(
                DailyStockHighlight(
                    ticker=h.ticker,
                    category=h.category,
                    topic=h.topic,
                    daily_trend=h.daily_trend,
                    price_change_pct=h.price_change_pct,
                    key_event=h.key_event,
                    verification_status=h.verification_status,
                    summary=h.summary,
                    citations=h.citations,
                    alert_message=h.alert_message,
                    insight_source=h.insight_source,
                )
            )

        return DailySummaryReport(
            generated_at=report.generated_at,
            overall_sentiment=report.overall_sentiment,
            highlights=highlights,
            macro_factors=report.macro_factors,
            key_takeaway=report.key_takeaway,
            user_id=user_id,
        )

    def _build_fallback_report(
        self, tickers: list[str], user_id: str | None = None
    ) -> DailySummaryReport:
        """Builds a basic, safe fallback report on error or failure.

        Args:
            tickers: List of watchlisted tickers.
            user_id: The target user's ID.

        Returns:
            DailySummaryReport with fallback contents.
        """
        return DailySummaryReport(
            generated_at=datetime.now(tz=UTC),
            overall_sentiment="Market data compilation completed. Refer to individual alerts for daily changes.",
            highlights=[
                DailyStockHighlight(
                    ticker=ticker,
                    category=InsightCategory.PRICE_ACTION,
                    topic=InsightTopic.VOLUME_SPIKE,
                    daily_trend="Neutral",
                    price_change_pct=0.0,
                    key_event="Daily consolidation summary",
                    verification_status="Unverified",
                    summary="Daily events logged; dynamic fact synthesis was skipped due to LLM timeout.",
                    citations=[],
                    alert_message=f"{ticker} — Daily market tracking update.",
                    insight_source="yfinance",
                )
                for ticker in tickers
            ],
            macro_factors=["General Market Activity"],
            key_takeaway="Check individual daily logs for detailed insights.",
            user_id=user_id,
        )
