"""Research Report Compiler.

Builds a structured, cited research report for a single ticker by combining
live yFinance fundamentals with the company's latest SEC 10-K filing excerpt,
synthesized via OpenAI Structured Outputs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import redis
from openai import OpenAIError

from config.settings import settings
from src.core.models import FinancialContext
from src.core.schemas import ResearchReportLLMOutput, ResearchReportResponse, Source
from src.data_sources.edgar_source import EdgarSource
from src.data_sources.yfinance_source import YFinanceDataSource
from src.llm.litellm_router import LiteLLMStructuredClient, get_structured_llm_client
from src.llm.prompts import PromptLoader
from src.utils.logger import get_logger
from src.utils.postprocessor import ResponsePostprocessor
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)

# Fundamentals and filings don't move intraday - 6h keeps reports fresh without
# re-running an LLM call on every request for a popular ticker.
_REPORT_CACHE_TTL_SECONDS = 6 * 3600
_CACHE_KEY = "research:report:{ticker}"

# Keep the filing excerpt small enough to stay well within prompt token budgets.
_FILING_EXCERPT_MAX_CHARS = 8_000


class ResearchReportCompiler:
    """Compiles a single-ticker research report from yfinance + SEC EDGAR."""

    def __init__(
        self,
        openai_client: LiteLLMStructuredClient | None = None,
        redis_client: Any | None = None,
    ) -> None:
        """Initialise compiler with required network dependencies.

        Args:
            openai_client: Structured-output client (FreeLLMAPI-primary,
                OpenAI-fallback via litellm) instance.
            redis_client: Redis client instance for caching.
        """
        self._client = openai_client or get_structured_llm_client()
        self._redis = redis_client or get_async_redis()
        self._postprocessor = ResponsePostprocessor()

    async def get_or_generate_report(self, ticker: str) -> ResearchReportResponse:
        """Return a cached report for `ticker`, or generate and cache a new one.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").

        Returns:
            A ResearchReportResponse.

        Raises:
            YFinanceError: If the ticker's market data can't be fetched at all.
        """
        ticker = ticker.upper().strip()
        cache_key = _CACHE_KEY.format(ticker=ticker)

        try:
            cached = await self._redis.get(cache_key)
            if cached:
                logger.info("[RESEARCH_REPORT_CACHE_HIT] Ticker: %s", ticker)
                report = ResearchReportResponse.model_validate_json(cached)
                report.from_cache = True
                return report
        except (redis.exceptions.RedisError, ConnectionError, OSError, ValueError) as exc:
            logger.warning("[RESEARCH_REPORT_CACHE_ERROR] Redis read failed: %s", exc)

        logger.info("[RESEARCH_REPORT_CACHE_MISS] Ticker: %s | Generating", ticker)
        report = await self._compile_report(ticker)

        try:
            await self._redis.set(
                cache_key, report.model_dump_json(), ex=_REPORT_CACHE_TTL_SECONDS
            )
        except (redis.exceptions.RedisError, ConnectionError, OSError, ValueError) as exc:
            logger.warning("[RESEARCH_REPORT_CACHE_WRITE_ERROR] Redis write failed: %s", exc)

        return report

    async def _compile_report(self, ticker: str) -> ResearchReportResponse:
        """Fetch data from both sources and synthesize the report.

        Raises:
            YFinanceError: If market data for `ticker` can't be fetched at all.
        """
        data_source = YFinanceDataSource()
        yf_data = await data_source.fetch(ticker, include_financials=True)
        financial_context = FinancialContext(**yf_data)

        filing_excerpt, filing_source = await self._fetch_latest_filing(ticker)

        prompt = PromptLoader.load(
            "user/research_report",
            ticker=ticker,
            financial_context=financial_context.to_context_string(),
            filing_excerpt=filing_excerpt
            or "_No recent 10-K filing found for this ticker._",
        )
        system_prompt = PromptLoader.load("system/research_report")

        parsed = await self._synthesize(ticker, system_prompt, prompt)

        sources = [
            Source(
                source="Yahoo Finance",
                source_type="yfinance",
                ticker=ticker,
                data_type="financial_data",
                id=ticker,
                retrieved_at=datetime.now(UTC).isoformat(),
            )
        ]
        if filing_source:
            sources.append(filing_source)

        financial_context_dict = financial_context.model_dump()
        warnings, confidence = self._run_postprocessing(
            ticker, parsed, financial_context_dict, len(sources)
        )

        return ResearchReportResponse(
            ticker=ticker,
            company_name=financial_context.company_name,
            generated_at=datetime.now(UTC).isoformat(),
            summary=parsed.summary,
            valuation_take=parsed.valuation_take,
            growth_take=parsed.growth_take,
            risk_take=parsed.risk_take,
            filing_highlights=parsed.filing_highlights,
            financial_context=financial_context_dict,
            sources=sources,
            confidence=confidence,
            warnings=warnings,
            from_cache=False,
        )

    async def _synthesize(
        self, ticker: str, system_prompt: str, user_prompt: str
    ) -> ResearchReportLLMOutput:
        """Call the LLM for structured research synthesis."""
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=settings.query_analysis_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=ResearchReportLLMOutput,
                temperature=0.2,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Structured research report generation returned null")
            return parsed
        except (OpenAIError, ValueError, KeyError, TypeError) as exc:
            logger.error("[RESEARCH_REPORT_LLM_ERROR] Ticker: %s | %s", ticker, exc)
            raise

    def _run_postprocessing(
        self,
        ticker: str,
        parsed: ResearchReportLLMOutput,
        financial_context_dict: dict[str, Any],
        citation_count: int,
    ) -> tuple[list[str], float]:
        """Run anti-hallucination checks and estimate confidence for the report."""
        keyed_context = {ticker: financial_context_dict}
        _, financial_warnings = self._postprocessor.validate_financial_context(
            keyed_context
        )
        combined_text = " ".join(
            [parsed.summary, parsed.valuation_take, parsed.growth_take, parsed.risk_take]
        )
        _, text_warnings = self._postprocessor.validate_response_text(
            combined_text, keyed_context
        )
        confidence = self._postprocessor.estimate_confidence(
            has_financial_context=True,
            has_citations=True,
            citation_count=citation_count,
            used_web_search=False,
        )
        return financial_warnings + text_warnings, confidence

    async def _fetch_latest_filing(
        self, ticker: str
    ) -> tuple[str | None, Source | None]:
        """Fetch the latest 10-K excerpt for `ticker`. Never raises - degrades gracefully."""
        edgar = EdgarSource()
        try:
            filings = await edgar.get_filings(ticker, filing_type="10-K", limit=1)
            if not filings:
                return None, None

            filing = filings[0]
            text = await edgar.get_filing_text(
                filing["primary_document_url"], max_chars=_FILING_EXCERPT_MAX_CHARS
            )
            if not text:
                return None, None

            source = Source(
                source="SEC EDGAR",
                source_type="sec_filing",
                ticker=ticker,
                data_type="filing",
                url=filing["primary_document_url"],
                id=filing.get("accession_number"),
                retrieved_at=datetime.now(UTC).isoformat(),
            )
            return text, source
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("[RESEARCH_REPORT_EDGAR_ERROR] Ticker: %s | %s", ticker, exc)
            return None, None
        finally:
            await edgar.close()
