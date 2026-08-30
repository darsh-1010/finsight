"""Ticker Resolution Service with dependency injection.

Resolves company names to stock ticker symbols.
"""

import asyncio
import json
import re

import redis
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings
from src.core.exceptions import TickerResolutionError
from src.core.interfaces import IDataSource, ITickerService
from src.core.types import JsonDict, ValidationStatus
from src.data_sources.yfinance_source import YFinanceDataSource
from src.llm.litellm_router import get_chat_model
from src.llm.prompts import PromptLoader
from src.utils.json_parser import LLMResponseParser
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis
from src.utils.ticker_lookup import resolve as static_resolve

logger = get_logger(__name__)


class TickerService(ITickerService):
    """Ticker resolution service.

    Resolves company names to stock ticker symbols using LLM
    and validates against data source.
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        data_source: IDataSource | None = None,
        validate_tickers: bool | None = None,
        model_name: str | None = None,
    ):
        """Initialize ticker service with dependencies.

        Args:
            llm: LLM client instance
            data_source: Data source for ticker validation
            validate_tickers: Whether to validate resolved tickers (defaults to settings)
            model_name: Model to use if llm not provided (defaults to settings)
        """
        # Use settings for defaults
        model_name = model_name or settings.ticker_resolution_model
        validate_tickers = (
            validate_tickers
            if validate_tickers is not None
            else settings.validate_tickers
        )

        self.llm = llm or get_chat_model(
            model_name, temperature=settings.ticker_resolution_temperature
        )
        self._data_source = data_source
        self.validate_tickers = validate_tickers
        self._resolution_semaphore = asyncio.Semaphore(
            settings.max_parallel_resolutions
        )

        # Load prompt from file
        system_prompt = PromptLoader.load("system/ticker_resolution")
        user_prompt = PromptLoader.load("user/ticker_resolution")
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", user_prompt)]
        )

        logger.info(f"TickerService initialized: validate={validate_tickers}")

    @property
    def data_source(self) -> IDataSource:
        """Get data source (lazy init if not provided)."""
        if self._data_source is None:
            self._data_source = YFinanceDataSource()

        data_source = self._data_source
        if data_source is None:
            raise RuntimeError("TickerService data source failed to initialize")
        return data_source

    async def resolve(self, name: str, context: str = "") -> JsonDict:
        """Resolve a company name to a ticker symbol.

        Resolution order (fastest-first):
          1. Static lookup  — yahoo_finance_tickers.json (0ms, ~1110 companies)
          2. Redis cache    — previously-resolved results (1ms)
          3. LLM resolution — TickerService LLM + yFinance validation (1-3s)

        Fallback is always the LLM path — nothing silently fails.
        """
        async with self._resolution_semaphore:
            logger.info(f"[TICKER] Resolving ticker: {name[:50]}...")

            # Normalise cache key so 'HDFC Bank', 'HDFC Bank Ltd', 'hdfc bank' share one entry
            _normalised_name = re.sub(r"\s+", " ", name.strip().lower())
            cache_key = f"ticker_cache:{_normalised_name}"

            try:
                # ── Level 1: Static lookup (0ms, no network, no LLM) ──────────────────
                # Covers ~1110 companies from yahoo_finance_tickers.json.
                # Returns None for unknowns OR for genuinely ambiguous names (e.g. bare
                # 'HDFC' could be Bank or Life) — those fall through to LLM which uses
                # conversation context to disambiguate correctly.
                static_ticker = static_resolve(name)
                if static_ticker:
                    result: JsonDict = {
                        "company_name": name,
                        "ticker": static_ticker,
                        "confidence": 1.0,
                        "exchange": None,
                        "alternatives": [],
                        "validation_status": ValidationStatus.VALIDATED.value,
                        "disambiguation": "static_lookup",
                        "error": None,
                    }
                    logger.info(f"[TICKER] Static HIT: '{name}' → {static_ticker}")
                    return result

                # ── Level 2: Redis cache (1ms, avoids repeat LLM calls) ───────────────
                try:
                    cached = await asyncio.to_thread(get_redis().get, cache_key)
                    if cached:
                        result = json.loads(cached)
                        logger.info(
                            f"[TICKER] Cache HIT for '{name}' → {result.get('ticker')}"
                        )
                        return result
                except (
                    AttributeError,
                    TypeError,
                    ValueError,
                    RuntimeError,
                    redis.exceptions.RedisError,
                ) as cache_err:
                    # RedisError (e.g. ConnectionError when Redis is briefly down) isn't
                    # a subclass of any builtin caught above - must be listed explicitly
                    # or a Redis outage crashes resolution instead of skipping the cache.
                    logger.debug(f"[TICKER] Cache lookup skipped: {cache_err}")

                # ── Level 3: LLM resolution ────────────────────────────────────────────
                chain = self._prompt | self.llm
                response = await chain.ainvoke(
                    {
                        "query": name,
                        "context": context or "None provided",
                    }
                )

                content = response.content
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif isinstance(item, dict) and "text" in item:
                            text_parts.append(str(item["text"]))
                    content_text = "".join(text_parts)
                else:
                    content_text = str(content)

                parsed = LLMResponseParser.parse(content_text)

                result = {
                    "company_name": parsed.get("company_name", name),
                    "ticker": parsed.get("ticker"),
                    "confidence": parsed.get("confidence", 0.0),
                    "exchange": parsed.get("exchange"),
                    "alternatives": parsed.get("alternatives", []),
                    "validation_status": ValidationStatus.UNVALIDATED.value,
                    "error": None,
                }

                if self.validate_tickers and result["ticker"]:
                    result = await self._validate(result)

                confidence = result.get("confidence", 0.0)
                if confidence >= settings.ticker_high_confidence:
                    result["disambiguation"] = "high_confidence"
                elif confidence >= settings.ticker_medium_confidence:
                    result["disambiguation"] = "medium_confidence"
                    result["warning"] = (
                        f"Moderate confidence for '{name}' → {result['ticker']}"
                    )
                else:
                    result["disambiguation"] = "low_confidence"
                    result["warning"] = (
                        f"Low confidence for '{name}' → {result['ticker']}"
                    )

                logger.info(
                    f"[TICKER] Resolved: {result['ticker']} "
                    f"(conf={result['confidence']:.2f}, status={result['validation_status']})"
                )

                if (
                    result["ticker"]
                    and result["validation_status"] != ValidationStatus.FAILED.value
                ):
                    try:
                        await asyncio.to_thread(
                            get_redis().setex,
                            cache_key,
                            settings.ticker_cache_ttl,
                            json.dumps(result),
                        )
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        RuntimeError,
                        redis.exceptions.RedisError,
                    ) as cache_err:
                        logger.debug(f"[TICKER] Cache write failed: {cache_err}")

                return result

            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(f"[TICKER] Resolution failed for '{name}': {e}")
                raise TickerResolutionError(
                    f"Failed to resolve ticker for '{name}': {e}"
                ) from e

    async def resolve_multiple(
        self, names: list[str], context: str = ""
    ) -> list[JsonDict]:
        """Resolve multiple company names in parallel.

        Args:
            names: List of company names
            context: Shared context

        Returns:
            List of resolution results
        """
        if not names:
            return []

        logger.info(f"Resolving {len(names)} tickers in parallel")

        tasks = [self.resolve(name, context) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        resolutions: list[JsonDict] = []
        for name, result in zip(names, results, strict=True):
            if isinstance(result, BaseException):
                logger.error(f"Failed to resolve {name}: {result}")
                resolutions.append(
                    {
                        "company_name": name,
                        "ticker": None,
                        "confidence": 0.0,
                        "validation_status": ValidationStatus.FAILED.value,
                        "error": str(result),
                    }
                )
            else:
                resolutions.append(result)

        return resolutions

    async def _validate(self, result: JsonDict) -> JsonDict:
        """Validate ticker by checking yFinance fast_info (lightweight, no full info fetch).

        Replaces the previous approach of calling data_source.validate() which used
        stock.info — the heaviest yFinance call (1-2s). fast_info only fetches price
        metadata and is ~5x faster.

        Alternatives are validated in PARALLEL (asyncio.gather) instead of sequentially.
        """
        import yfinance as _yf

        async def _check_fast(ticker_sym: str) -> bool:
            """Check existence via fast_info.last_price — lightweight (~200ms)."""
            try:
                price = await asyncio.to_thread(
                    lambda: _yf.Ticker(ticker_sym).fast_info.last_price
                )
                return price is not None and float(price) > 0
            except (AttributeError, TypeError, ValueError, RuntimeError):
                return False

        ticker = result["ticker"]

        try:
            # Validate primary ticker
            if await _check_fast(ticker):
                result["validation_status"] = ValidationStatus.VALIDATED.value
                logger.debug("[TICKER] Validated via fast_info: %s", ticker)
                return result

            # Primary failed — validate all alternatives IN PARALLEL
            alternatives = result.get("alternatives", [])
            if not alternatives:
                result["validation_status"] = ValidationStatus.UNVALIDATED.value
                result["error"] = "Primary ticker invalid, no alternatives"
                return result

            logger.info(
                "[TICKER] Primary %s failed, checking %d alternatives in parallel",
                ticker,
                len(alternatives),
            )
            validation_results = await asyncio.gather(
                *[_check_fast(alt) for alt in alternatives], return_exceptions=True
            )

            for alt, valid in zip(alternatives, validation_results, strict=True):
                if valid is True:
                    result["ticker"] = alt
                    result["validation_status"] = ValidationStatus.VALIDATED.value
                    logger.info("[TICKER] Alternative validated: %s → %s", ticker, alt)
                    return result

            result["validation_status"] = ValidationStatus.UNVALIDATED.value
            result["error"] = (
                f"Primary and all {len(alternatives)} alternatives failed validation"
            )

        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.warning("[TICKER] Validation error for %s: %s", ticker, e)
            result["validation_status"] = ValidationStatus.UNVALIDATED.value
            result["error"] = f"Validation error: {e}"

        return result
