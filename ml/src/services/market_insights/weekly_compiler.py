# pylint: disable=too-many-lines
"""Weekly Compiler Service for Market Insights.

Dynamically scans the global stock market using a curated universe of 100 tickers,
calculates technical indicators (RSI and volume surge ratios), and synthesizes a
structured, tier-tailored weekly report using OpenAI Structured Outputs.
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
from src.services.market_insights.models import (
    AlertPayload,
    InsightCategory,
    InsightTopic,
    WeeklyStockHighlight,
    WeeklySummaryReport,
    WeeklySummaryReportTier1,
    WeeklySummaryReportTier2,
    WeeklySummaryReportTier3,
    WeeklySummaryReportTier4,
)
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)

# Cache time-to-live: 24 hours (86,400 seconds)
_REPORT_CACHE_TTL_SECONDS = 86_400
_GLOBAL_TIER_REPORT_KEY = "mi:weekly_report:tier:{tier_id}"


class WeeklySummaryCompiler:
    """Service to dynamically scan market-mover tickers and compile tiered weekly reports.

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

    _MACRO_UNIVERSE = [
        # Major Global Indices & Benchmarks
        "^SPX",  # S&P 500 Index (Broad US Equity Market)
        "^IXIC",  # Nasdaq Composite Index (Tech Sector Benchmark)
        "^TNX",  # 10-Year Treasury Yield (Interest Rates / Bond Market)
        "GC=F",  # Gold Futures (Inflation / Safe Haven Benchmark)
        "CL=F",  # Crude Oil Futures (Energy / Commodity Benchmark)
        "BTC-USD",  # Bitcoin USD (Digital Assets / Crypto Benchmark)
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

        self._redis = redis_client or get_async_redis()

    async def get_or_generate_summary(
        self,
        user_id: str,
        raw_alerts: list[AlertPayload],
        user_tier: int = 1,
    ) -> WeeklySummaryReport:
        """Retrieve cached weekly summary globally by tier or compile and cache a new one.

        Args:
            user_id: Target user unique identifier.
            raw_alerts: Unused daily alerts list (maintained for API interface compatibility).
            user_tier: The user's subscription tier (1-4).

        Returns:
            A WeeklySummaryReport instance.
        """
        cache_key = _GLOBAL_TIER_REPORT_KEY.format(tier_id=user_tier)
        try:
            cached_data = await self._redis.get(cache_key)
            if cached_data:
                logger.info(
                    "[WEEKLY_REPORT_CACHE_HIT] Tier: %d | User: %s", user_tier, user_id
                )
                report = WeeklySummaryReport.model_validate_json(cached_data)
                report.user_id = user_id
                return report
        except (
            redis.exceptions.RedisError,
            ConnectionError,
            OSError,
            ValueError,
        ) as exc:
            logger.warning("[WEEKLY_REPORT_CACHE_ERROR] Redis read failed: %s", exc)

        logger.info(
            "[WEEKLY_REPORT_CACHE_MISS] Tier: %d | Serving instant fallback and triggering background compile",
            user_tier,
        )
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
    ) -> WeeklySummaryReport | None:
        """Asynchronously compiles, caches, and logs audit entries for a tier report under a lock.

        Args:
            user_id: Target user unique identifier.
            raw_alerts: Unused daily alerts list.
            user_tier: The user's subscription tier (1-4).

        Returns:
            A WeeklySummaryReport instance if compiled, or None if skipped.
        """
        lock_key = f"mi:weekly_report:lock:tier:{user_tier}"
        cache_key = _GLOBAL_TIER_REPORT_KEY.format(tier_id=user_tier)

        try:
            # Acquire distributed Redis lock for 180 seconds to prevent concurrent runs
            acquired = await self._redis.set(lock_key, "locked", ex=180, nx=True)
            if not acquired:
                logger.info(
                    "[WEEKLY_REPORT_LOCK_SKIPPED] Tier: %d is already compiling under another worker",
                    user_tier,
                )
                return None
        except (redis.exceptions.RedisError, ConnectionError, OSError) as exc:
            logger.warning(
                "[WEEKLY_REPORT_LOCK_ERROR] Distributed lock failed: %s", exc
            )

        try:
            logger.info(
                "[WEEKLY_REPORT_BACKGROUND_COMPILE] Tier: %d starting compilation",
                user_tier,
            )
            report = await self._compile_report(user_id, raw_alerts, user_tier)

            try:
                await self._redis.set(
                    cache_key, report.model_dump_json(), ex=_REPORT_CACHE_TTL_SECONDS
                )
                logger.info(
                    "[WEEKLY_REPORT_CACHE_POPULATED] Tier: %d cached successfully",
                    user_tier,
                )
            except (
                redis.exceptions.RedisError,
                ConnectionError,
                OSError,
                ValueError,
            ) as exc:
                logger.warning(
                    "[WEEKLY_REPORT_CACHE_WRITE_ERROR] Redis write failed: %s", exc
                )

            try:
                date_str = datetime.now(UTC).strftime("%Y-%m-%d")
                audit_key = f"mi:weekly_report:audit:tier:{user_tier}:{date_str}"
                await self._redis.set(
                    audit_key, report.model_dump_json(), ex=30 * 86400
                )
                logger.info(
                    "[WEEKLY_REPORT_AUDIT_LOGGED] Tier: %d saved to audit storage",
                    user_tier,
                )
            except (
                redis.exceptions.RedisError,
                ConnectionError,
                OSError,
                ValueError,
            ) as exc:
                logger.warning(
                    "[WEEKLY_REPORT_AUDIT_WRITE_ERROR] Redis audit log failed: %s", exc
                )

            return report
        finally:
            try:
                await self._redis.delete(lock_key)
            except (redis.exceptions.RedisError, ConnectionError, OSError) as exc:
                logger.warning(
                    "[WEEKLY_REPORT_LOCK_RELEASE_ERROR] Failed to release lock: %s", exc
                )

    async def _fetch_movers_and_news(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
        """Fetch 6-month yFinance prices, scan movers, and harvest news in parallel.

        Returns:
            Tuple of (all_movers_list, macro_items_list, parallel_news_results).
        """
        loop = asyncio.get_running_loop()
        combined_universe = self._SCANNING_UNIVERSE + self._MACRO_UNIVERSE
        logger.info(
            "[WEEKLY_SCAN_START] Beginning batch yFinance download for %d tickers",
            len(combined_universe),
        )
        data = await loop.run_in_executor(
            None,
            lambda: yf.download(
                combined_universe, period="6mo", group_by="ticker", progress=False
            ),
        )
        logger.info(
            "[WEEKLY_SCAN_DOWNLOAD_COMPLETE] Batch download finished. Data shape: %s",
            data.shape,
        )
        gainers, losers = self._scan_market_movers(data)
        logger.info(
            "[WEEKLY_SCAN_MOVERS] Identified %d gainers and %d losers meeting the +-5%% threshold",
            len(gainers),
            len(losers),
        )
        all_movers = gainers + losers

        macro_items = []
        if isinstance(data.columns, pd.MultiIndex) and not data.empty:
            for ticker in self._MACRO_UNIVERSE:
                if ticker not in data.columns.levels[0]:
                    continue
                metrics = self._calculate_stock_metrics(data[ticker])
                if not metrics:
                    continue
                macro_items.append(
                    {
                        "ticker": ticker,
                        "start_price": metrics["start_price"],
                        "end_price": metrics["end_price"],
                        "weekly_change_pct": metrics["weekly_change_pct"],
                        "rsi": metrics["rsi"],
                        "volume_ratio": metrics["volume_ratio"],
                    }
                )

        combined_tickers = all_movers + macro_items
        logger.info(
            "[WEEKLY_NEWS_START] Initiating parallel news harvesting for %d items",
            len(combined_tickers),
        )
        news_results = await asyncio.gather(
            *(self._fetch_mover_news_async(m["ticker"]) for m in combined_tickers)
        )
        logger.info("[WEEKLY_NEWS_FETCH_COMPLETE] Completed news harvesting.")
        return all_movers, macro_items, news_results

    async def _fetch_websearch_events(self) -> list[dict[str, Any]]:
        """Retrieve top 5-7 key global financial market events via OpenAI built-in web search.

        Uses the OpenAI Responses API with the `web_search` hosted tool, which is natively
        powered by the same OPENAI_API_KEY — no external dependencies required.
        Cited source URLs are extracted from the response annotation objects.

        Returns:
            List of dictionaries with title, content, and url keys.
        """
        logger.info(
            "[WEEKLY_WEB_SEARCH_START] Fetching top market events via OpenAI web search"
        )
        query = (
            "List the top 7 most important global events from this week that might affect "
            "the global financial system, global economy, or financial markets. "
            "Search for significant occurrences across the following areas:\n"
            "1. Macroeconomic developments (central bank decisions, inflation, interest rates, GDP, trade policies).\n"
            "2. Geopolitical events and global policy changes (conflicts, "
            "international relations, major government transitions).\n"
            "3. Regulatory/Risk changes (major SEC investigations, massive "
            "regulatory fines, global risk developments).\n"
            "4. Major corporate actions or sector/industry shifts (M&A "
            "activity, supply chain disruptions, competitive shifts).\n"
            "5. Broad price actions (commodity price shocks, major index moves).\n"
            "Focus on any event that has a global financial footprint or "
            "economic consequence, not just basic stock price moves. "
            "Format each event as: [Event Title] — [1-2 sentence factual summary]."
        )
        try:
            response = await self._client.responses.create(
                model=os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini"),
                tools=[{"type": "web_search_preview"}],
                input=query,
            )

            # Extract cited URLs from response annotations
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
                "[WEEKLY_WEB_SEARCH_COMPLETE] Retrieved %d citations from OpenAI web search",
                len(cited_urls),
            )

            # Return a unified list: one entry per event with the full synthesized
            # text as content and each distinct citation URL as the source
            events: list[dict[str, Any]] = []
            for idx, cited in enumerate(cited_urls[:7]):
                events.append(
                    {
                        "title": cited["title"] or f"Market Event #{idx + 1}",
                        "content": synthesized_text,
                        "url": cited["url"],
                    }
                )

            # If the model returned text but no annotations, return the raw text as one event
            if not events and synthesized_text:
                events.append(
                    {
                        "title": "Weekly Market Digest",
                        "content": synthesized_text,
                        "url": "",
                    }
                )

            return events

        except (RuntimeError, ConnectionError, ValueError, OSError) as exc:
            logger.warning(
                "[WEEKLY_WEB_SEARCH_ERROR] OpenAI web search failed: %s", exc
            )
            return []

    async def _compile_report(
        self,
        user_id: str,
        raw_alerts: list[AlertPayload],
        user_tier: int = 1,
    ) -> WeeklySummaryReport:
        """Executes the global market scanning, filtering, news harvesting, and AI synthesis.

        Args:
            user_id: Target user identifier.
            raw_alerts: Weekly alerts list accumulated during the week.
            user_tier: The user's subscription tier.

        Returns:
            A synthesized WeeklySummaryReport.
        """
        try:
            # 1. Fetch yFinance movers & news and Tavily web events
            all_movers, macro_items, news_results = await self._fetch_movers_and_news()
            web_events = await self._fetch_websearch_events()

            # 2. Build synthesis prompt with hybrid context
            prompt = self._build_synthesis_prompt_v2(
                self._build_yf_context(all_movers, news_results[: len(all_movers)]),
                web_events,
                raw_alerts,
                self._build_yf_context(macro_items, news_results[len(all_movers) :]),
            )
            instructions, response_format = self._get_tier_prompts_and_format(user_tier)

            completion = await self._client.beta.chat.completions.parse(
                model=os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a premium financial intelligence analyst. Your goal is to "
                            "synthesize a weekly report containing a balanced mix of stock movers "
                            "and broader global financial/macroeconomic events.\n\n"
                            "HIGHLIGHT MIX REQUIREMENT:\n"
                            "Your generated `highlights` list must NOT be exclusively about individual stocks. "
                            "You MUST include at least 2 to 3 highlights that analyze broader macroeconomic "
                            "or global financial world events (such as central bank interest rate decisions, "
                            "inflation reports like CPI, geopolitical risk developments, or index-level "
                            "performance like the S&P 500 or Treasury yields).\n\n"
                            "TICKER & TAGGING REQUIREMENT:\n"
                            "For macroeconomic and global highlights, represent them in the `ticker` field using "
                            "either the asset's standard ticker symbol (e.g., `^SPX` for S&P 500, `^TNX` for "
                            "10-Year Bond Yield, `GC=F` for Gold, `CL=F` for Oil, `BTC-USD` for Bitcoin) or an "
                            'uppercase descriptive event tag (e.g., `"FED"` for interest rates, `"CPI"` for '
                            'inflation, `"GEOPOL"` for geopolitics, `"REGULATORY"` for risk/fines).\n\n'
                            "CLASSIFICATION REQUIREMENT:\n"
                            "For each stock or macroeconomic/global highlight, you must classify the primary "
                            "driver of the event into one of the 6 high-level categories and one of the 30 "
                            "strict topics. Populate the `category` and `topic` fields exactly.\n\n"
                            "DATA PROVENANCE & INSIGHT SOURCE REQUIREMENT:\n"
                            "Every highlight must track its source in the `insight_source` field:\n"
                            "- Set `insight_source` strictly to 'yfinance' for highlights derived from "
                            "weekly movers, macro benchmarks, or the alerts queue.\n"
                            "- Set `insight_source` strictly to 'websearch' for highlights derived from "
                            "the live web search key events.\n\n"
                            "Provide exact URLs/links from the news/web results supporting each highlight. "
                            "For yfinance news/alerts, use the provided links; for websearch events, use "
                            "the provided source urls.\n\n"
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
                raise ValueError("Structured weekly report generation returned null")

            logger.info(
                "[WEEKLY_REPORT_SYNTHESIS_COMPLETE] LLM report synthesized successfully for Tier: %d | User: %s",
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
            logger.error("[WEEKLY_COMPILER_LLM_ERROR] Synthesis failed: %s", exc)
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
        """Calculate performance and technical indicators for a single stock.

        Args:
            df: Historical daily pricing DataFrame for a single ticker.

        Returns:
            Dictionary of computed metrics, or None if data is insufficient.
        """
        clean_df = df.dropna(subset=["Close"])
        if len(clean_df) < 35:
            return None

        # 1. Weekly Return (last 5 active trading days)
        start_close = float(clean_df["Close"].iloc[-5])
        end_close = float(clean_df["Close"].iloc[-1])
        weekly_change = (
            ((end_close - start_close) / start_close * 100) if start_close > 0 else 0.0
        )

        # 2. RSI (14-day)
        diffs = clean_df["Close"].diff()
        avg_gain = diffs.clip(lower=0).ewm(com=13, min_periods=14).mean()
        avg_loss = (-diffs.clip(upper=0)).ewm(com=13, min_periods=14).mean()
        current_rsi = float(
            (100 - (100 / (1 + (avg_gain / avg_loss.replace(0, 1e-9))))).iloc[-1]
        )

        # 3. Volume Ratio (last 5 days average vs 30-day baseline)
        baseline_vol = clean_df["Volume"].iloc[-35:-5].mean()
        volume_ratio = (
            (clean_df["Volume"].iloc[-5:].mean() / baseline_vol)
            if baseline_vol > 0
            else 1.0
        )

        return {
            "start_price": round(start_close, 2),
            "end_price": round(end_close, 2),
            "weekly_change_pct": round(weekly_change, 2),
            "rsi": round(current_rsi, 1),
            "volume_ratio": round(volume_ratio, 2),
        }

    def _scan_market_movers(
        self, data: pd.DataFrame
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Filters the top 10 gainers and top 10 losers from the stock data.

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
                "weekly_change_pct": metrics["weekly_change_pct"],
                "rsi": metrics["rsi"],
                "volume_ratio": metrics["volume_ratio"],
            }

            if metrics["weekly_change_pct"] >= 5.0:
                gainers.append(item)
            elif metrics["weekly_change_pct"] <= -5.0:
                losers.append(item)

        # Volatility Fallback
        if len(gainers) < 10 or len(losers) < 10:
            logger.info(
                "[VOLATILITY_FALLBACK] Fewer than 10 tickers met threshold. Using absolute ranks."
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
                        "weekly_change_pct": metrics["weekly_change_pct"],
                        "rsi": metrics["rsi"],
                        "volume_ratio": metrics["volume_ratio"],
                    }
                )
            all_items.sort(key=lambda x: x["weekly_change_pct"], reverse=True)
            return all_items[:10], sorted(
                all_items[-10:], key=lambda x: x["weekly_change_pct"]
            )

        gainers.sort(key=lambda x: x["weekly_change_pct"], reverse=True)
        losers.sort(key=lambda x: x["weekly_change_pct"])

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
                "[YFINANCE_NEWS_ERROR] Failed to fetch news for ticker %s: %s",
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
                alerts.append(f"Overbought Momentum Warning (RSI: {item['rsi']})")
            elif item["rsi"] <= 30.0:
                alerts.append(f"Oversold Reversion Opportunity (RSI: {item['rsi']})")

            if item["volume_ratio"] >= 2.0:
                alerts.append(
                    f"Institutional Volume Surge ({item['volume_ratio']}x average)"
                )

            weekly_trend = "Neutral"
            if item["weekly_change_pct"] > 1.5:
                weekly_trend = "Bullish"
            elif item["weekly_change_pct"] < -1.5:
                weekly_trend = "Bearish"

            yf_context.append(
                {
                    "ticker": item["ticker"],
                    "weekly_trend": weekly_trend,
                    "weekly_change_pct": item["weekly_change_pct"],
                    "start_price": item["start_price"],
                    "end_price": item["end_price"],
                    "rsi": item["rsi"],
                    "volume_ratio": item["volume_ratio"],
                    "technical_alerts": alerts,
                    "articles": news_results[idx],
                }
            )
        return yf_context

    def _build_synthesis_prompt_v2(
        self,
        yf_context: list[dict[str, Any]],
        web_events: list[dict[str, Any]] | None = None,
        raw_alerts: list[AlertPayload] | None = None,
        macro_context: list[dict[str, Any]] | None = None,
    ) -> str:
        """Formats the calculated market scan movers and news context into a clear prompt.

        Args:
            yf_context: Calculated trends, technicals, and news.
            web_events: List of web search key events context.
            raw_alerts: List of raw alert payloads from the database/queue.
            macro_context: Calculated macroeconomic benchmarks and index details.

        Returns:
            Formatted prompt string.
        """
        sections = ["=== GLOBAL WEEKLY SCAN MOVERS & TECHNICAL METRICS ==="]
        for item in yf_context:
            sections.append(
                f"\nTicker: {item['ticker']} | Calculated Weekly Trend: {item['weekly_trend']} | "
                f"Start Price: ${item['start_price']} | End Price: ${item['end_price']} | "
                f"Weekly Change: {item['weekly_change_pct']}% | RSI: {item['rsi']} | "
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

        if macro_context:
            sections.append("\n=== GLOBAL MACROECONOMIC & ASSET BENCHMARKS ===")
            for item in macro_context:
                sections.append(
                    f"\nBenchmark Ticker: {item['ticker']} | Calculated Weekly Trend: {item['weekly_trend']} | "
                    f"Start Value/Price: ${item['start_price']} | End Value/Price: ${item['end_price']} | "
                    f"Weekly Change: {item['weekly_change_pct']}% | RSI: {item['rsi']} | "
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
            "Address any detected market alerts in the summaries. "
            "Make sure to categorize and map each highlight to its proper category/topic."
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
            instructions = (
                "You are an Elite Institutional Financial Analyst. Your goal is to synthesize the "
                "user's weekly stock alerts and macroeconomic/global benchmarks (S&P 500, Gold, Oil, Bitcoin, "
                "Bond Yields) with live yFinance news and calculated stock trends. Deliver "
                "a dense, institutional-grade, highly quantitative recap. Focus heavily on valuation "
                "metrics, earnings, absolute support/resistance price targets, macro-economic drivers, "
                "and risk profiles. Do not simplify terms; use professional financial language.\n"
                "Word constraints (strict, do not violate):\n"
                "- Stock highlight summary: Up to 510 words per highlight. Format strictly as follows: "
                "First, write a detailed paragraph of at least 3-4 long, "
                "informative sentences defining the core event/benchmark movement, explaining what is "
                "going on, trends, primary drivers, and broader market context. "
                "Then, provide pointwise bullet points covering the major parts of "
                "the insight (such as valuation metrics, "
                "earnings details, support/resistance price targets, and volatility/risk factors). For "
                "macroeconomic highlights (like ^SPX, ^TNX, FED, CPI), focus the bullets on global yield changes, "
                "inflation figures, commodity rates, or policy impacts rather than individual stock earnings.\n"
                "- Overall sentiment: Up to 510 words (deep macro-economic and market-wide trend synthesis).\n"
                "- Key takeaway: Up to 310 words (dense strategic guidance, portfolio asset allocation and "
                "risk advice).\n\n"
                "PUSH NOTIFICATION REQUIREMENT:\n"
                "For each highlight, you MUST also generate a dynamic `alert_message` field "
                "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
                "'{Company/Event Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
                "For event-based highlights (like FED, CPI), you can format as:\n"
                "'{Event Name} — [one-sentence insight]'\n"
                "Keep the message under 110 characters total."
            )
            return instructions, WeeklySummaryReportTier4

        # Tier 3: Pro
        if user_tier == 3:
            instructions = (
                "You are a Senior Wealth Management Portfolio Manager. Your goal is to synthesize weekly "
                "stock watchlist alerts and macroeconomic/global indicators with live yFinance news and "
                "calculated trends. Deliver a highly detailed, professional-grade wealth summary. Explain "
                "the 'why' behind price movements, sector rotation, analyst ratings, and macro policies "
                "in professional but clear terms.\n"
                "Word constraints:\n"
                "- Stock highlight summary: Up to 260 words per highlight. Format strictly as follows: "
                "First, write a detailed paragraph of at least 3 full, informative sentences defining the "
                "core event/benchmark and explaining what is going on in detail (primary drivers, price catalysts). "
                "Then, provide pointwise bullet points covering the major parts of "
                "the insight (price drivers, catalysts, "
                "news details, volume). For macro highlights (like ^SPX, ^TNX, FED, CPI), focus the bullets "
                "on interest rates, yield curves, commodity price catalysts, or index levels.\n"
                "- Overall sentiment: Up to 310 words (comprehensive sector performance and market summary).\n"
                "- Key takeaway: Up to 210 words (actionable strategic wealth advice and portfolio "
                "recommendations).\n\n"
                "PUSH NOTIFICATION REQUIREMENT:\n"
                "For each highlight, you MUST also generate a dynamic `alert_message` field "
                "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
                "'{Company/Event Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
                "For event-based highlights (like FED, CPI), you can format as:\n"
                "'{Event Name} — [one-sentence insight]'\n"
                "Keep the message under 110 characters total."
            )
            return instructions, WeeklySummaryReportTier3

        # Tier 2: Basic
        if user_tier == 2:
            instructions = (
                "You are a Personal Financial Advisor. Your goal is to synthesize the user's stock watchlist "
                "alerts and macroeconomic/global events with live yFinance news and trends. Provide a clean, "
                "explanatory, and clear narrative for an active retail investor. Avoid overwhelming "
                "terminology, but explain the core catalysts behind price and volume moves.\n"
                "Word constraints:\n"
                "- Stock highlight summary: Up to 110 words per highlight. Provide a detailed paragraph of "
                "at least 2-3 sentences explaining what is going on in the event based on news. "
                "Do NOT include technical metrics (weekly change, RSI, volume ratio) inside the paragraph field. "
                "Populate the metrics fields (weekly_change, rsi, volume_ratio) strictly with their "
                "values (e.g. '+9.14%', '61.6', '1.75x') without any brackets.\n"
                "For macroeconomic highlights that are event-based and don't have natural calculations, "
                "set `weekly_change` to '0.0%', `rsi` to 'N/A', and `volume_ratio` to 'N/A' (or populate "
                "them with the provided calculations if using a macro ticker like ^SPX or ^TNX).\n"
                "- Overall sentiment: Up to 160 words (accessible summary of overall weekly market behavior).\n"
                "- Key takeaway: Up to 110 words (actionable clear investment lesson or key takeaway).\n\n"
                "PUSH NOTIFICATION REQUIREMENT:\n"
                "For each highlight, you MUST also generate a dynamic `alert_message` field "
                "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
                "'{Company/Event Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
                "For event-based highlights (like FED, CPI), you can format as:\n"
                "'{Event Name} — [one-sentence insight]'\n"
                "Keep the message under 110 characters total."
            )
            return instructions, WeeklySummaryReportTier2

        # Tier 1: Free (Default fallback)
        instructions = (
            "You are a Financial News Editor. Your goal is to synthesize the stock watchlist alerts "
            "and macroeconomic/global indicators with live yFinance news. Provide an informative, "
            "research-backed weekly summary explaining key catalysts in simple and clear terms.\n"
            "Word constraints:\n"
            "- Stock highlight summary: Up to 100 words per highlight. Provide a paragraph of "
            "at least 2-3 sentences explaining what is going on in the event based on news. "
            "Do NOT include technical metrics (weekly change, RSI, volume ratio) inside the paragraph field. "
            "Populate the metrics fields (weekly_change, rsi, volume_ratio) strictly with their "
            "values (e.g. '+9.14%', '61.6', '1.75x') without any brackets.\n"
            "For macroeconomic highlights that are event-based and don't have natural calculations, "
            "set `weekly_change` to '0.0%', `rsi` to 'N/A', and `volume_ratio` to 'N/A' (or populate "
            "them with the provided calculations if using a macro ticker like ^SPX or ^TNX).\n"
            "- Overall sentiment: Up to 120 words (brief market narrative in simple, clear terms).\n"
            "- Key takeaway: Up to 80 words (accessible weekly lesson in simple terms).\n\n"
            "PUSH NOTIFICATION REQUIREMENT:\n"
            "For each highlight, you MUST also generate a dynamic `alert_message` field "
            "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
            "'{Company/Event Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
            "For event-based highlights (like FED, CPI), you can format as:\n"
            "'{Event Name} — [one-sentence insight]'\n"
            "Keep the message under 110 characters total."
        )
        return instructions, WeeklySummaryReportTier1

    def _normalize_report(
        self, report: Any, user_id: str | None = None
    ) -> WeeklySummaryReport:
        """Normalises any tier-specific summary report back to the standard WeeklySummaryReport schema.

        Args:
            report: Tier-specific WeeklySummaryReport model (Tier 1-4).
            user_id: The target user's ID.

        Returns:
            A standard WeeklySummaryReport instance.
        """
        highlights = []
        for h in report.highlights:
            if isinstance(h.summary, str):
                summary_str = h.summary
            else:
                summary_str = (
                    f"{h.summary.paragraph}\n"
                    f"- Weekly Change: {h.summary.weekly_change}\n"
                    f"- RSI: {h.summary.rsi}\n"
                    f"- Volume Ratio: {h.summary.volume_ratio}"
                )

            highlights.append(
                WeeklyStockHighlight(
                    ticker=h.ticker,
                    category=h.category,
                    topic=h.topic,
                    weekly_trend=h.weekly_trend,
                    price_change_pct=h.price_change_pct,
                    key_event=h.key_event,
                    verification_status=h.verification_status,
                    summary=summary_str,
                    citations=h.citations,
                    alert_message=h.alert_message,
                    insight_source=h.insight_source,
                )
            )

        return WeeklySummaryReport(
            generated_at=report.generated_at,
            overall_sentiment=report.overall_sentiment,
            highlights=highlights,
            macro_factors=report.macro_factors,
            key_takeaway=report.key_takeaway,
            user_id=user_id,
        )

    def _build_fallback_report(
        self, tickers: list[str], user_id: str | None = None
    ) -> WeeklySummaryReport:
        """Builds a basic, safe fallback report on error or failure.

        Args:
            tickers: List of watchlisted tickers.
            user_id: The target user's ID.

        Returns:
            WeeklySummaryReport with fallback contents.
        """
        return WeeklySummaryReport(
            generated_at=datetime.now(tz=UTC),
            overall_sentiment="Market data compilation completed. Refer to individual alerts for daily changes.",
            highlights=[
                WeeklyStockHighlight(
                    ticker=ticker,
                    category=InsightCategory.PRICE_ACTION,
                    topic=InsightTopic.VOLUME_SPIKE,
                    weekly_trend="Neutral",
                    price_change_pct=0.0,
                    key_event="Weekly consolidation summary",
                    verification_status="Unverified",
                    summary="Daily events logged; dynamic fact synthesis was skipped due to LLM timeout.",
                    citations=[],
                    alert_message=f"{ticker} — Weekly market tracking update.",
                    insight_source="yfinance",
                )
                for ticker in tickers
            ],
            macro_factors=["General Market Activity"],
            key_takeaway="Check individual daily logs for detailed insights.",
            user_id=user_id,
        )
