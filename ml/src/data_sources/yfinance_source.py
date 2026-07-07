"""yFinance data source implementation."""

import asyncio
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, cast

import pandas as pd
import yfinance as yf
from langchain_core.documents import Document

from config.settings import settings
from src.core.exceptions import YFinanceError
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

try:
    from curl_cffi.requests import Session as CurlCffiSession
except ImportError:  # pragma: no cover - covered through runtime fallback tests
    CurlCffiSession = None

logger = get_logger(__name__)

# FIX-007: Module-level TTL cache for yFinance full-data fetches.
# Financial statements and company info change daily; ratios/prices update every few minutes.
# TTL of 5 minutes balances freshness vs API call reduction.
# Capped at 200 tickers. Real-time price calls bypass this cache entirely.
_YFINANCE_CACHE: dict[str, dict] = {}  # key -> {"data": ..., "expires": float}
_YFINANCE_CACHE_TTL = 300  # 5 minutes — near-real-time for market data
_YFINANCE_CACHE_MAX = 200  # max tickers in memory

# Endpoints that _fetch_sync() services WITHOUT touching financial statement APIs.
# Derived directly from _fetch_sync() logic: everything that runs when include_financials=False.
# Used by query_service._fetch_ticker_context() to decide whether to skip heavy fetching.
#
# HOW TO MAINTAIN: if you add a new _fetch_*() method to _fetch_sync() that doesn't
# require financial statement APIs, add its LLM-facing endpoint name here.
# The LLM is prompted to return one of these names in expanded_queries[*].yfinance.endpoint.
#
# Safety rule: if the LLM returns an endpoint name NOT in this set, include_financials
# defaults to True — guaranteed safe, never silently wrong.
LIGHTWEIGHT_ENDPOINTS: frozenset[str] = frozenset(
    {
        # Price / quote
        "price",
        "fast_info",
        "quote",
        "current_price",
        "live_price",
        "market_price",
        "last_price",
        # Historical OHLCV
        "history",
        "ohlcv",
        "historical",
        "price_history",
        "chart",
        # Volume
        "volume",
        # Basic info (does NOT require the heavy .info dict — these come from fast_info)
        "ticker_info",
        "ticker",
        "symbol",
    }
)


class YFinanceDataSource(BaseDataSource):
    """Data source implementation for yFinance.

    Provides access to stock information, historical data, financials,
    and analyst recommendations from Yahoo Finance.
    """

    def __init__(self) -> None:
        """Initialize the yFinance data source."""
        self._browser_session: Any | None = None
        self._fetch_semaphore = asyncio.Semaphore(
            settings.max_parallel_yfinance_fetches
        )
        self._session_lock = threading.Lock()
        self._browser_session_warning_logged = False

    @property
    def name(self) -> str:
        return "yfinance"

    def _build_browser_session(self) -> Any | None:
        """Build a browser-impersonated session for Yahoo Finance."""
        if not settings.yfinance_use_browser_session:
            return None

        if CurlCffiSession is None:
            if not self._browser_session_warning_logged:
                logger.warning(
                    "[YFINANCE_SESSION_FALLBACK] Reason: curl_cffi_missing | Transport: default"
                )
                self._browser_session_warning_logged = True
            return None

        return CurlCffiSession(
            impersonate=cast(Any, settings.yfinance_impersonate),
            timeout=settings.yfinance_http_timeout_seconds,
        )

    def _get_browser_session(self) -> Any | None:
        """Return the shared browser-impersonated session."""
        if self._browser_session is not None:
            return self._browser_session

        with self._session_lock:
            if self._browser_session is None:
                self._browser_session = self._build_browser_session()
            return self._browser_session

    def _build_ticker(self, ticker: str) -> yf.Ticker:
        """Create a ticker instance using the configured HTTP transport."""
        session = self._get_browser_session()
        if session is None:
            return yf.Ticker(ticker)
        return yf.Ticker(ticker, session=session)

    async def _run_with_limit(self, function: Any, *args: Any) -> Any:
        """Run synchronous yFinance work under the shared concurrency cap."""
        async with self._fetch_semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, function, *args)

    @timed("yfinance.fetch", warn_threshold_s=3.0)
    async def fetch(self, identifier: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch comprehensive stock data for a ticker (TTL-cached, FIX-007)."""
        ticker = identifier.upper().strip()
        period = kwargs.get("period", settings.default_history_period)
        include_financials = kwargs.get(
            "include_financials", settings.include_financials
        )
        include_recommendations = kwargs.get(
            "include_recommendations", settings.include_recommendations
        )

        # Build deterministic cache key
        cache_key = (
            f"{ticker}::{period}::{include_financials}::{include_recommendations}"
        )
        entry = _YFINANCE_CACHE.get(cache_key)
        if entry and time.monotonic() < entry["expires"]:
            logger.info(
                "[YFINANCE_CACHE] HIT ticker=%s (TTL=%ds)", ticker, _YFINANCE_CACHE_TTL
            )
            return entry["data"]

        logger.info("Fetching yFinance data: ticker=%s period=%s", ticker, period)

        try:
            data = await self._run_with_limit(
                self._fetch_sync,
                ticker,
                period,
                include_financials,
                include_recommendations,
            )

            # Write to cache (evict one entry if at capacity)
            if len(_YFINANCE_CACHE) >= _YFINANCE_CACHE_MAX:
                oldest_key = next(iter(_YFINANCE_CACHE))
                del _YFINANCE_CACHE[oldest_key]
            _YFINANCE_CACHE[cache_key] = {
                "data": data,
                "expires": time.monotonic() + _YFINANCE_CACHE_TTL,
            }
            logger.info("[YFINANCE_CACHE] SET ticker=%s", ticker)

            return data

        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            error_msg = str(e)
            if "404" in error_msg or "Not Found" in error_msg:
                logger.warning(
                    "yFinance data not found (expected for invalid tickers): ticker=%s",
                    ticker,
                )
            else:
                logger.error(
                    "Failed to fetch yFinance data: ticker=%s error=%s",
                    ticker,
                    error_msg,
                )

            raise YFinanceError(
                f"Failed to fetch data for ticker {ticker}",
                details={"ticker": ticker, "error": str(e)},
            ) from e

    async def validate(self, identifier: str) -> bool:
        """Validate if a ticker exists and has data."""
        ticker = identifier.upper().strip()
        try:
            data = await self.get_real_time_price(ticker)
            return data.get("price") is not None
        except (ValueError, TypeError, AttributeError, RuntimeError):
            return False

    def _get_currency_symbol(self, currency_code: str | None) -> str:
        """Get currency symbol from code."""
        if not currency_code:
            return "$"

        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "INR": "₹",
            "JPY": "¥",
            "CNY": "¥",
            "CAD": "C$",
            "AUD": "A$",
            "HKD": "HK$",
            "SGD": "S$",
        }
        return symbols.get(currency_code.upper(), f"{currency_code} ")

    def _fetch_sync(
        self,
        ticker: str,
        period: str,
        include_financials: bool,
        include_recommendations: bool,
    ) -> dict[str, Any]:
        """Synchronous data fetch orchestrator."""
        stock = self._build_ticker(ticker)

        # 1. Basic Data
        fast_info = self._fetch_fast_info(stock, ticker)
        info = self._fetch_info(stock, ticker)

        # 2. Historical Data
        history_data = self._fetch_history(stock, ticker, period)

        # 3. Financials
        financials = (
            self._fetch_all_financials(stock, ticker) if include_financials else {}
        )

        # 4. Recommendations
        recommendations = {}
        if include_recommendations:
            recommendations = self._fetch_recommendations(stock, ticker)

        # Assemble raw data dict
        data = {
            "ticker": ticker,
            "fetched_at": datetime.utcnow().isoformat(),
            "fast_info": fast_info,
            "info": info,
            **history_data,
            **financials,
            **recommendations,
        }

        # 5. Flatten & Standardize
        return self._standardize_data(data)

    def _fetch_fast_info(self, stock: yf.Ticker, ticker: str) -> dict[str, Any]:
        """Fetch fast_info attributes."""
        fast_info_dict = {}
        try:
            if hasattr(stock, "fast_info"):
                keys = [
                    "last_price",
                    "previous_close",
                    "year_high",
                    "year_low",
                    "day_high",
                    "day_low",
                    "currency",
                ]
                for key in keys:
                    try:
                        val = getattr(stock.fast_info, key, None)
                        if val is not None:
                            fast_info_dict[key] = val
                    except (ValueError, TypeError, AttributeError, RuntimeError):
                        pass
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Failed to fetch fast_info for %s: %s", ticker, e)
        return fast_info_dict

    def _fetch_info(self, stock: yf.Ticker, ticker: str) -> dict[str, Any]:
        """Fetch and clean stock info."""
        try:
            info = stock.info
            return {
                "name": info.get("longName", info.get("shortName", ticker)),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "price": info.get("currentPrice", info.get("regularMarketPrice")),
                "previous_close": info.get("previousClose"),
                "open": info.get("open"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "volume": info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "description": info.get("longBusinessSummary"),
                "book_value": info.get("bookValue"),
                "price_to_book": info.get("priceToBook"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "total_assets": info.get("totalAssets"),
                "total_debt": info.get("totalDebt"),
                "total_revenue": info.get("totalRevenue"),
                "revenue_per_share": info.get("revenuePerShare"),
                "profit_margins": info.get("profitMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                "earnings_per_share": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "peg_ratio": info.get("pegRatio"),
                "enterprise_value": info.get("enterpriseValue"),
                "ev_to_revenue": info.get("enterpriseToRevenue"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                "currency": info.get("currency"),
                "regularMarketChange": info.get("regularMarketChange"),
                "regularMarketChangePercent": info.get("regularMarketChangePercent"),
            }
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Failed to fetch stock info: ticker=%s error=%s", ticker, e)
            return {}

    def _fetch_history(
        self, stock: yf.Ticker, ticker: str, period: str
    ) -> dict[str, Any]:
        """Fetch historical data and summary."""
        result: dict[str, Any] = {"history": [], "history_summary": {}}
        try:
            history = stock.history(period=period)
            if not history.empty:
                result["history"] = self._dataframe_to_dict(history)

                # Calculate summary stats
                start_price = float(history["Close"].iloc[0])
                end_price = float(history["Close"].iloc[-1])
                price_change_pct = ((end_price - start_price) / start_price) * 100

                result["history_summary"] = {
                    "period": period,
                    "start_date": history.index[0].strftime("%Y-%m-%d"),
                    "end_date": history.index[-1].strftime("%Y-%m-%d"),
                    "start_price": start_price,
                    "end_price": end_price,
                    "high": float(history["High"].max()),
                    "low": float(history["Low"].min()),
                    "max_volume": float(history["Volume"].max()),
                    "min_volume": float(history["Volume"].min()),
                    "avg_volume": float(history["Volume"].mean()),
                    "price_change_pct": float(price_change_pct),
                }
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Failed to fetch history: ticker=%s error=%s", ticker, e)
        return result

    def _fetch_all_financials(self, stock: yf.Ticker, ticker: str) -> dict[str, Any]:
        """Fetch all financial statements."""
        result: dict[str, Any] = {}

        result["income_statement"] = self._fetch_statement(stock, "income_stmt", ticker)
        result["balance_sheet"] = self._fetch_statement(stock, "balance_sheet", ticker)
        result["cash_flow"] = self._fetch_statement(stock, "cashflow", ticker)

        # Generate summary string from income statement
        if result["income_statement"]:
            result["financials_summary"] = self._format_financial_statement(
                ticker, "income_statement", result["income_statement"]
            )

        return result

    def _fetch_statement(
        self, stock: yf.Ticker, attr: str, ticker: str
    ) -> list[dict[str, Any]]:
        """Fetch single financial statement."""
        try:
            stmt = getattr(stock, attr)
            if stmt is not None and not stmt.empty:
                return self._dataframe_to_dict(stmt.T.head(4))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Failed to fetch %s: ticker=%s error=%s", attr, ticker, e)
        return []

    def _fetch_recommendations(self, stock: yf.Ticker, ticker: str) -> dict[str, Any]:
        """Fetch analyst recommendations."""
        result: dict[str, Any] = {
            "recommendations": [],
            "recommendations_summary": None,
        }
        try:
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                recent = recs.tail(10)
                result["recommendations"] = self._dataframe_to_dict(recent)
                result["recommendations_summary"] = self._format_recommendations(
                    ticker, result["recommendations"]
                )
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning(
                "Failed to fetch recommendations: ticker=%s error=%s", ticker, e
            )
        return result

    def _standardize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Flatten and standardize data structure."""
        fast_info = data.get("fast_info", {})
        info = data.get("info", {})

        # Merge prices
        data["current_price"] = fast_info.get("last_price") or info.get("price")
        data["previous_close"] = fast_info.get("previous_close") or info.get(
            "previous_close"
        )

        # Calculate changes
        if data["current_price"] and data["previous_close"]:
            change = data["current_price"] - data["previous_close"]
            data["price_change"] = change
            data["price_change_pct"] = (change / data["previous_close"]) * 100

        # Map fields to flat structure
        fields_map = {
            "company_name": "name",
            "sector": "sector",
            "industry": "industry",
            "exchange": "exchange",
            "description": "description",
            "market_cap": "market_cap",
            "pe_ratio": "pe_ratio",
            "forward_pe": "forward_pe",
            "book_value": "book_value",
            "price_to_book": "price_to_book",
            "dividend_yield": "dividend_yield",
            "beta": "beta",
            "shares_outstanding": "shares_outstanding",
            "earnings_per_share": "earnings_per_share",
        }

        for target, source in fields_map.items():
            data[target] = info.get(source)

        data["currency"] = fast_info.get("currency") or info.get("currency")

        # Performance Metrics
        data["week_52_high"] = fast_info.get("year_high") or info.get("52_week_high")
        data["week_52_low"] = fast_info.get("year_low") or info.get("52_week_low")
        data["day_high"] = fast_info.get("day_high") or info.get("day_high")
        data["day_low"] = fast_info.get("day_low") or info.get("day_low")
        data["volume"] = info.get("volume")
        data["avg_volume"] = info.get("avg_volume")

        # Data Quality Check
        req_fields = ["company_name", "market_cap", "pe_ratio", "current_price"]
        present = sum(1 for f in req_fields if data.get(f) is not None)

        if present == len(req_fields):
            data["data_quality"] = "complete"
        elif present > 0:
            data["data_quality"] = "partial"
        else:
            data["data_quality"] = "minimal"

        return data

    def _dataframe_to_dict(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Convert DataFrame to list of dictionaries."""
        if df.empty:
            return []

        df_reset = df.reset_index()
        for col in df_reset.columns:
            if pd.api.types.is_datetime64_any_dtype(df_reset[col]):
                df_reset[col] = df_reset[col].dt.strftime("%Y-%m-%d")

        records = df_reset.where(pd.notna(df_reset), None).to_dict(orient="records")
        return [{str(k): v for k, v in record.items()} for record in records]

    def _format_financial_statement(
        self,
        ticker: str,
        stmt_type: str,
        data: list[dict[str, Any]],
        currency: str = "$",
    ) -> str:
        """Format financial statement as text."""
        type_names = {
            "income_statement": "Income Statement",
            "balance_sheet": "Balance Sheet",
            "cash_flow": "Cash Flow Statement",
        }
        name = type_names.get(stmt_type, stmt_type)
        lines = [f"# {ticker} - {name}", ""]

        for period in data[:4]:
            date = period.get("index", "Unknown")
            lines.append(f"## Period: {date}")
            for k, v in period.items():
                if k != "index" and v is not None:
                    val = (
                        f"{currency}{v:,.0f}"
                        if isinstance(v, (int, float)) and abs(v) > 1000
                        else str(v)
                    )
                    lines.append(f"- {k}: {val}")
            lines.append("")
        return "\n".join(lines)

    def _format_recommendations(self, ticker: str, recs: list[dict[str, Any]]) -> str:
        """Format recommendations as text."""
        if not recs:
            return "No recent analyst recommendations available."

        lines = [f"# {ticker} - Analyst Recommendations", ""]
        for rec in recs[-10:]:
            firm = rec.get("Firm", "Unknown")
            grade = rec.get("To Grade", rec.get("toGrade", "N/A"))
            lines.append(f"- **{firm}**: {grade}")
        return "\n".join(lines)

    async def validate_connection(self) -> bool:
        """Validate yFinance connection."""
        try:
            stock = await self._run_with_limit(self._build_ticker, "AAPL")
            info = await self._run_with_limit(lambda: stock.info)
            return bool(info and info.get("symbol"))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error("yFinance connection validation failed: %s", e)
            return False

    async def get_real_time_price(self, ticker: str) -> dict[str, Any]:
        """Get real-time price data."""
        ticker = ticker.upper().strip()
        try:

            def _fetch():
                stock = self._build_ticker(ticker)
                info = stock.info
                return {
                    "ticker": ticker,
                    "price": info.get("currentPrice", info.get("regularMarketPrice")),
                    "change": info.get("regularMarketChange"),
                    "percent": info.get("regularMarketChangePercent"),
                }

            return await self._run_with_limit(_fetch)
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error("Failed to fetch real-time price: %s", e)
            raise YFinanceError(f"Failed to fetch real-time price for {ticker}") from e

    def to_documents(self, data: dict[str, Any]) -> list[Document]:
        """Convert fetched data to documents."""
        ticker = data.get("ticker", "UNKNOWN")
        info = data.get("info", {})
        currency = info.get("currency", "USD")
        symbol = self._get_currency_symbol(currency)

        docs = []

        # 1. Company Info Document
        if info:
            content = (
                f"Company: {info.get('name', ticker)}\n"
                f"Sector: {info.get('sector', 'N/A')}\n"
                f"Industry: {info.get('industry', 'N/A')}\n"
                f"Description:\n{info.get('description', 'N/A')}\n"
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": self.name,
                        "ticker": ticker,
                        "type": "company_info",
                    },
                )
            )

        # 2. Market Data
        price = data.get("current_price")
        if price:
            content = (
                f"{ticker} Market Data\n"
                f"Price: {symbol}{price}\n"
                f"Change: {data.get('price_change_pct', 0):.2f}%\n"
                f"Market Cap: {data.get('market_cap', 'N/A')}\n"
                f"P/E: {data.get('pe_ratio', 'N/A')}\n"
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": self.name,
                        "ticker": ticker,
                        "type": "market_data",
                    },
                )
            )

        return docs
