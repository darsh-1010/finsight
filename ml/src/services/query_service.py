"""Query Intelligence Service.

Orchestrates query analysis, ticker resolution, and data fetching.
"""

import asyncio
import hashlib
from typing import Any, Dict, List, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config.settings import settings
from src.core.exceptions import QueryAnalysisError
from src.core.interfaces import IDataSource, IQueryService, ITickerService
from src.core.models import (
    FinancialContext,
    MultiTickerContext,
    QueryEntities,
    QueryExpansionResult,
)
from src.core.types import JsonDict
from src.data_sources.yfinance_source import LIGHTWEIGHT_ENDPOINTS, YFinanceDataSource
from src.llm.prompts import PromptLoader
from src.services.ticker_service import TickerService
from src.utils.json_parser import LLMResponseParser
from src.utils.logger import get_logger
from src.utils.perf_utils import timed

logger = get_logger(__name__)


class QueryService(IQueryService):
    """Query analysis and expansion service.

    Integrated Query Intelligence engine that handles:
    1. Dynamic intent classification
    2. Entity extraction and ticker resolution
    3. Multi-source data fetching
    4. Context assembly
    """

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        ticker_service: ITickerService | None = None,
        data_source: IDataSource | None = None,
        **kwargs: Any,
    ):
        """Initialize query service with dependencies.

        Args:
            llm: LLM client instance
            ticker_service: Ticker resolution service
            data_source: Data source for fetching financial data
            model_name: Model to use if llm not provided (defaults to settings)
            temperature: Temperature for LLM responses (defaults to settings)
        """
        # Use settings for defaults
        model_name = kwargs.get("model_name") or settings.query_analysis_model
        temperature = kwargs.get("temperature") or settings.query_analysis_temperature

        # FIX-006: Model tiering — fast model for simple queries, full model for complex analysis.
        # If a custom llm is injected, use it for both (maintains backward compat).
        if llm is not None:
            self.llm = llm
            self._fast_llm = llm
        else:
            self.llm = ChatOpenAI(model=model_name, temperature=temperature)
            # Fast model for intent/slot-filling queries (simple definitions, single data lookups)
            fast_model = settings.gpt_4o_mini  # gpt-4.1-mini by default
            self._fast_llm = ChatOpenAI(model=fast_model, temperature=temperature)

        self._ticker_service = ticker_service
        self._data_source = data_source
        self.temperature = temperature
        self.model_name = model_name

        # Load prompts
        system_prompt = PromptLoader.load("system/query_expansion")
        user_prompt = PromptLoader.load("user/query_expansion")
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", user_prompt)]
        )

        # Build both chains — full and fast
        self._chain: Any = self._prompt | self.llm
        self._fast_chain: Any = self._prompt | self._fast_llm

        logger.info(
            "QueryService initialized (model=%s, fast_model=%s)",
            self.model_name,
            fast_model if llm is None else self.model_name,
        )

    # FIX-006: Keywords that signal complex financial reasoning requiring the full model.
    # Anything not matched routes to the fast model (saves 10-30s on simple queries).
    _COMPLEX_SIGNALS = frozenset(
        {
            # Original signals
            "compare",
            "comparison",
            "analyse",
            "analyze",
            "analysis",
            "forecast",
            "predict",
            "prediction",
            "risk",
            "recommend",
            "portfolio",
            "allocation",
            "strategy",
            "should i",
            "vs",
            "versus",
            "best",
            "worst",
            "rank",
            "ranking",
            "valuation",
            "dcf",
            "intrinsic value",
            "fair value",
            "explain why",
            "why did",
            "why is",
            "what caused",
            "outlook",
            "trend",
            "projection",
            "scenario",
            # FIX: Missing analytical signals — these imply deep reasoning not slot-filling
            # Price movement analysis (always needs full model for root-cause reasoning)
            "why",
            "explain",
            "reason",
            "cause",
            "caused",
            "fell",
            "dropped",
            "slipped",
            "declined",
            "crashed",
            "tanked",
            "surged",
            "rose",
            "rallied",
            "jumped",
            "spiked",
            "soared",
            "underperform",
            "outperform",
            # Investment decision signals (need full reasoning not just data lookup)
            "buy",
            "sell",
            "hold",
            "worth",
            "good investment",
            "invest",
            "should",
            "would you",
            "is it",
            # Sentiment and qualitative signals
            "sentiment",
            "consensus",
            "analyst",
            "target price",
            "upgrade",
            "downgrade",
            "bullish",
            "bearish",
            "overvalued",
            "undervalued",
        }
    )

    def _select_chain(self, query: str) -> Any:
        """Route query to fast or full LLM chain based on complexity signals."""
        q_lower = query.lower()
        if any(signal in q_lower for signal in self._COMPLEX_SIGNALS):
            logger.info("[MODEL_TIER] Selection: Full | Model: %s", self.model_name)
            return self._chain
        logger.info(
            "[MODEL_TIER] Selection: Fast | Model: %s", self._fast_llm.model_name
        )
        return self._fast_chain

    @property
    def ticker_service(self) -> ITickerService:
        """Get ticker service (lazy init if not provided)."""
        if self._ticker_service is None:
            self._ticker_service = TickerService(
                llm=self.llm, data_source=self.data_source
            )
        return self._ticker_service

    @property
    def data_source(self) -> IDataSource:
        """Get data source (lazy init if not provided)."""
        if self._data_source is None:
            self._data_source = YFinanceDataSource()
        data_source = self._data_source
        if data_source is None:
            raise RuntimeError("QueryService data source failed to initialize")
        return data_source

    @timed("query.analyze", warn_threshold_s=3.0)
    async def analyze(self, query: str) -> dict[str, Any]:
        """Analyze query to extract intent, entities and specific requirements."""
        request_id = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()[:6]
        logger.info(
            "[QUERY_ANALYSIS_START] ReqId: %s | Query: %s", request_id, query[:50]
        )

        try:
            # 1. LLM Analysis
            response_content = await self._invoke_analysis_llm(query, request_id)
            parsed = LLMResponseParser.parse(response_content)

            # 2. Validation & Enrichment
            result = self._parse_and_validate_analysis(parsed, query)

            # 3. Entity Resolution
            await self._resolve_missing_tickers(result, query, request_id)

            self._log_analysis_result(result, request_id)
            return result.model_dump()

        except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as e:
            logger.error("[ANALYSIS_FAILED] ReqId: %s | Error: %s", request_id, e)
            raise QueryAnalysisError(f"Failed to analyze query: {e}") from e

    async def _invoke_analysis_llm(self, query: str, request_id: str) -> str:
        """Invoke the appropriate LLM chain and extract content."""
        logger.debug("[LLM_INVOKE] ReqId: %s | Action: Analysis", request_id)
        response = await self._select_chain(query).ainvoke({"user_query": query})
        content = response.content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    text_parts.append(str(item["text"]))
            return "".join(text_parts)
        return str(content)

    def _parse_and_validate_analysis(
        self, parsed: dict, query: str
    ) -> QueryExpansionResult:
        """Validate parsed LLM response and ensure follow-ups exist."""
        if not parsed.get("query_identifier"):
            parsed["query_identifier"] = self._generate_query_id(query)

        result = QueryExpansionResult(**parsed)
        self._ensure_follow_ups(result)
        return result

    async def _resolve_missing_tickers(
        self, result: QueryExpansionResult, query: str, request_id: str
    ) -> None:
        """Resolve tickers if company names found but no tickers."""
        ents = result.entities
        if ents.company_names and not ents.tickers:
            logger.info(
                "[TICKER_RESOLVE] ReqId: %s | Count: %d",
                request_id,
                len(ents.company_names),
            )
            tickers = await self._resolve_entities(ents.company_names, query)
            if tickers:
                ents.tickers = tickers
                logger.info(
                    "[TICKER_RESOLVE_SUCCESS] ReqId: %s | Tickers: %s",
                    request_id,
                    tickers,
                )

    def _log_analysis_result(
        self, result: QueryExpansionResult, request_id: str
    ) -> None:
        """Standardized logging of analysis results."""
        ents = result.entities
        logger.info(
            "[ANALYSIS_SUCCESS] ReqId: %s | Intent: %s | Confidence: %.2f | Tickers: %s",
            request_id,
            result.intent,
            result.confidence,
            ents.tickers,
        )

    def _ensure_follow_ups(self, result: QueryExpansionResult) -> None:
        """Ensure the result always has at least some follow-up questions."""
        if not result.suggested_follow_ups:
            logger.warning(
                "[ANALYSIS] No follow-ups generated by LLM, adding generic fallback"
            )
            ticker = result.get_primary_ticker()
            if ticker:
                result.suggested_follow_ups = [
                    f"What is the valuation outlook for {ticker}?",
                    f"How does {ticker}'s performance compare to its industry peers?",
                    f"What are the key risk factors for {ticker} in the current market?",
                ]
            elif self._is_personal_finance_intent(result.intent):
                result.suggested_follow_ups = [
                    "How much of my income should I save each month?",
                    "What is the difference between a Roth IRA and a Traditional IRA?",
                    "How does compound interest work for long-term savings?",
                ]
            else:
                result.suggested_follow_ups = [
                    "What are the top-performing stocks in this sector?",
                    "How are current macroeconomic trends affecting the market?",
                    "What are the latest analyst recommendations for the large-cap tech sector?",
                ]

    @staticmethod
    def _is_personal_finance_intent(intent: str) -> bool:
        """Detect if the LLM-generated intent describes a personal finance query.

        Used as a lightweight fallback check when no tickers are present and the
        LLM has not generated follow-up questions, so we can produce contextually
        relevant suggestions rather than defaulting to equity market follow-ups.
        """
        personal_finance_keywords = {
            "budget",
            "saving",
            "emergency",
            "debt",
            "mortgage",
            "retirement",
            "compound",
            "tax",
            "insurance",
            "credit",
            "educate",
            "personal",
            "fund",
            "loan",
            "income",
            "expense",
            "financial_literacy",
        }
        intent_lower = intent.lower()
        return any(kw in intent_lower for kw in personal_finance_keywords)

    @timed("query.analyze_and_fetch", warn_threshold_s=5.0)
    async def analyze_and_fetch(
        self,
        query: str,
        session_ticker: str | None = None,
    ) -> JsonDict:
        """Full pipeline: analyze, resolve tickers, fetch data."""
        request_id = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()[:6]
        logger.info("[PIPELINE_START] ReqId: %s | Query: %s", request_id, query[:50])

        try:
            # 1. Analysis Step
            expansion = await self._orchestrate_analysis_step(
                query, session_ticker, request_id
            )

            # 2. Identify Targets
            tickers = expansion.get_all_tickers()
            if not tickers:
                return self._finalize_no_tickers_result(expansion, request_id)

            # 3. Fetch Step
            logger.info(
                "[PIPELINE_FETCH] ReqId: %s | Count: %d", request_id, len(tickers)
            )
            contexts, errors = await self._orchestrate_fetch_step(
                tickers, expansion, request_id
            )

            return self._finalize_pipeline_result(
                expansion, contexts, errors, request_id
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as e:
            logger.error("[PIPELINE_ERROR] ReqId: %s | Error: %s", request_id, e)
            return {
                "status": "failed",
                "errors": [str(e)],
                "metadata": {"request_id": request_id},
            }

    async def _orchestrate_analysis_step(
        self, query: str, sess_tick: str | None, rid: str
    ) -> QueryExpansionResult:
        """Run analysis and handle session ticker injection."""
        expansion_data = await self.analyze(query)
        expansion = QueryExpansionResult(**expansion_data)

        ents: QueryEntities = getattr(expansion, "entities")
        if sess_tick and not ents.tickers:
            ents.tickers = [sess_tick]
            logger.info("[PIPELINE_INJECT] ReqId: %s | Ticker: %s", rid, sess_tick)

        return expansion

    async def _orchestrate_fetch_step(
        self, tickers: list[str], expansion: QueryExpansionResult, rid: str
    ) -> tuple[list[dict], list[str]]:
        """Run parallel data fetches."""
        fetch_tasks = [
            self._fetch_ticker_context(t, expansion=expansion) for t in tickers
        ]
        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        contexts = []
        errors = []
        for ticker, res in zip(tickers, fetch_results):
            if isinstance(res, BaseException):
                logger.error(
                    "[FETCH_ERROR] ReqId: %s | Ticker: %s | Error: %s", rid, ticker, res
                )
                errors.append(f"Failed to fetch {ticker}: {res}")
            elif res:
                contexts.append(res.model_dump())
        return contexts, errors

    def _finalize_no_tickers_result(
        self, expansion: QueryExpansionResult, rid: str
    ) -> JsonDict:
        """Handle case where no tickers were identified."""
        logger.warning("[PIPELINE_NO_TICKERS] ReqId: %s", rid)
        return {
            "status": "no_tickers",
            "expansion": expansion.model_dump(),
            "contexts": [],
            "errors": ["Could not identify or resolve any stock tickers"],
            "metadata": {"request_id": rid, **self._build_metadata(expansion)},
        }

    def _finalize_pipeline_result(
        self,
        expansion: QueryExpansionResult,
        contexts: list[dict],
        errors: list[str],
        rid: str,
    ) -> JsonDict:
        """Synthesize final pipeline response."""
        status = "success"
        if not contexts:
            status = "fetch_failed"
        elif errors:
            status = "partial_success"

        logger.info("[PIPELINE_COMPLETE] ReqId: %s | Status: %s", rid, status)
        return {
            "status": status,
            "expansion": expansion.model_dump(),
            "contexts": contexts,
            "errors": errors,
            "metadata": {"request_id": rid, **self._build_metadata(expansion)},
        }

    async def _resolve_entities(
        self, company_names: list[str], context: str
    ) -> list[str]:
        """Resolve company names to validated tickers."""
        if not company_names:
            return []

        logger.info(
            f"[RESOLUTION] Calling TickerService for {len(company_names)} companies..."
        )
        for i, name in enumerate(company_names, 1):
            logger.info(f"  [{i}] {name}")

        # Use TickerService to resolve multiple
        resolutions = await self.ticker_service.resolve_multiple(
            company_names, context=context
        )

        validated_tickers = [
            res["ticker"]
            for res in resolutions
            if res.get("ticker") and res.get("validation_status") == "validated"
        ]

        logger.info(
            f"[RESOLUTION] Validated {len(validated_tickers)}/{len(company_names)} tickers"
        )
        return validated_tickers

    @timed("query.fetch_ticker", warn_threshold_s=2.0)
    async def _fetch_ticker_context(
        self,
        ticker: str,
        expansion: QueryExpansionResult | None = None,
    ) -> FinancialContext:
        """Fetch and build FinancialContext for a single ticker.

        FIX: Uses expansion.expanded_queries[*].yfinance.endpoint to determine
        which yFinance endpoints are actually needed by the LLM's analysis plan.
        This eliminates 2-6s of redundant fetching for simple price/ratio queries.

        If no expansion is provided (or endpoints are ambiguous), falls back
        to full fetch to maintain backward compatibility.
        """
        # Determine if financials are needed based on LLM's endpoint requests.
        # APPROACH: whitelist of known-lightweight endpoints (defined in yfinance_source.py).
        # Logic: skip financials ONLY when ALL requested endpoints are confirmed lightweight.
        # Any unknown endpoint name → include_financials=True (safe default, never wrong).
        #
        # Why whitelist not blacklist? A blacklist of 'financial' endpoints breaks silently
        # when the LLM uses a new endpoint name (e.g. 'revenue', 'quarterly_earnings').
        # A whitelist is closed-world: anything not explicitly approved stays safe.
        include_financials = True  # default: always fetch everything

        if expansion and expansion.expanded_queries:
            requested_endpoints: set[str] = set()
            for eq in expansion.expanded_queries:
                if eq.yfinance and eq.yfinance.endpoint:
                    requested_endpoints.add(eq.yfinance.endpoint.lower())

            # issubset(): ALL requested endpoints must be lightweight to skip financials.
            # If even one endpoint is unknown or financial, include_financials stays True.
            if requested_endpoints and requested_endpoints.issubset(
                LIGHTWEIGHT_ENDPOINTS
            ):
                include_financials = False
                logger.info(
                    "[FETCH] %s: selective fetch — endpoints=%s ⊆ LIGHTWEIGHT, include_financials=False",
                    ticker,
                    requested_endpoints,
                )
            elif requested_endpoints:
                logger.debug(
                    "[FETCH] %s: endpoints=%s contain non-lightweight items, keeping include_financials=True",
                    ticker,
                    requested_endpoints,
                )

        logger.info(
            "[FETCH] Starting data fetch for %s (include_financials=%s)...",
            ticker,
            include_financials,
        )
        data = await self.data_source.fetch(
            ticker, include_financials=include_financials
        )
        logger.info("[FETCH] ✓ %s: Received %d data fields", ticker, len(data))
        return FinancialContext(**data)

    def _generate_query_id(self, query: str) -> str:
        """Generate deterministic query identifier."""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode(), usedforsecurity=False).hexdigest()[:8]

    def _build_metadata(self, expansion: QueryExpansionResult) -> JsonDict:
        """Build simple metadata dict."""
        return {
            "query_id": expansion.query_identifier,
            "intent": expansion.intent,
            "confidence": expansion.confidence,
            "is_comparative": expansion.is_comparative(),
            "ticker_count": len(expansion.entities.tickers),
        }

    def build_llm_context(
        self,
        expansion: QueryExpansionResult,
        contexts: list[FinancialContext],
        max_context_chars: int | None = None,
    ) -> str:
        """Build formatted context string for LLM response generation.

        Args:
            expansion: Query expansion result
            contexts: List of financial contexts
            max_context_chars: Maximum characters for context (defaults to settings)

        Returns:
            Formatted context string, truncated to budget if needed
        """
        max_context_chars = max_context_chars or settings.max_context_chars

        if not contexts:
            return "No financial data available."

        # Determine whether to include the longBusinessSummary (description field).
        # For price/ratio/earnings queries it's boilerplate that wastes 400-800 tokens.
        # Only include for overview/about/general queries where it genuinely adds value.
        overview_intents = {
            "overview",
            "about",
            "general",
            "introduction",
            "background",
            "describe",
            "what is",
            "who is",
            "profile",
            "business model",
        }
        intent_lower = (expansion.intent or "").lower()
        include_description = any(kw in intent_lower for kw in overview_intents)

        # Build header
        parts = [
            f"# Analysis: {expansion.core_question}",
            f"**Original Question**: {expansion.original_query}",
            f"**Intent**: {expansion.intent}",
            f"**Confidence**: {expansion.confidence:.0%}",
            "",
        ]

        if expansion.is_comparative():
            parts.append("**Analysis Type**: Comparative")

        parts.append("---\n")

        # Contexts (Single or Multi)
        if len(contexts) == 1:
            parts.append(
                contexts[0].to_context_string(
                    include_financials=True,
                    include_description=include_description,
                )
            )
        else:
            multi_ctx = MultiTickerContext(contexts=contexts)
            parts.append(multi_ctx.to_context_string())

        # Add key analysis dimensions
        if expansion.expanded_queries:
            parts.append("\n## Analysis Dimensions")
            sorted_queries = sorted(
                expansion.expanded_queries, key=lambda x: x.priority
            )
            for eq in sorted_queries:
                # Only include purpose (guidance) — drop the raw sub-question string
                # to avoid the LLM treating them as hard requirements that narrow its response.
                parts.append(f"- {eq.purpose}")

        # Add reasoning
        if expansion.reasoning:
            parts.append("\n## Analysis Notes")
            parts.append(expansion.reasoning)

        context_str = "\n".join(parts)
        return context_str
