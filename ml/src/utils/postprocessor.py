"""
Response postprocessor for anti-hallucination and quality assurance.

Validates LLM responses before returning to the client:
- Numeric sanity checks (price, market cap, PE ratio ranges)
- Citation validation (ensure cited data matches context)
- Confidence estimation based on data source availability
"""

import re
from typing import Any

from src.llm.prompts import PromptLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Reasonable ranges for financial metrics (for sanity checks)
SANITY_RANGES = {
    "current_price": (0.001, 100_000),  # $0.001 to $100,000
    "market_cap": (1_000, 50_000_000_000_000),  # $1K to $50T
    "pe_ratio": (-1000, 5000),  # Can be negative for loss-making
    "forward_pe": (-1000, 5000),
    "dividend_yield": (0, 100),  # 0% to 100%
    "beta": (-10, 10),
    "volume": (0, 50_000_000_000),  # Up to 50B shares
    "price_change_pct": (-99.9, 10000),  # -99.9% to 10000%
    "week_52_high": (0.001, 100_000),
    "week_52_low": (0.001, 100_000),
    "earnings_per_share": (-10_000, 10_000),
}


class ResponsePostprocessor:
    """Validates and enhances LLM responses before returning to the client."""

    def validate_financial_context(
        self,
        financial_context: dict | None,
    ) -> tuple[dict | None, list[str]]:
        """Validate financial data for sanity.

        Args:
            financial_context: Structured financial data dict

        Returns:
            Tuple of (cleaned context, warnings list)
        """
        if not financial_context:
            return financial_context, []

        warnings: list[str] = []

        for ticker, data in financial_context.items():
            if not isinstance(data, dict):
                continue

            for field, (low, high) in SANITY_RANGES.items():
                value = data.get(field)
                if value is not None and isinstance(value, (int, float)):
                    if value < low or value > high:
                        warnings.append(
                            PromptLoader.load(
                                "system/notices/out_of_range",
                                field=field,
                                ticker=ticker,
                                value=value,
                                low=low,
                                high=high,
                            )
                        )
                        # Mark as questionable but don't remove — let the consumer decide
                        data[f"_{field}_warning"] = "outside_expected_range"
                        logger.warning(
                            f"[POSTPROCESSOR] {ticker}.{field}={value} "
                            f"outside range [{low}, {high}]"
                        )

            # Cross-field validation
            price = data.get("current_price")
            high_52 = data.get("week_52_high")
            low_52 = data.get("week_52_low")

            if price and high_52 and price > high_52 * 1.1:
                warnings.append(
                    PromptLoader.load(
                        "system/notices/stale_data_high",
                        ticker=ticker,
                        price=price,
                        high_52=high_52,
                    )
                )
            if price and low_52 and price < low_52 * 0.9:
                warnings.append(
                    PromptLoader.load(
                        "system/notices/stale_data_low",
                        ticker=ticker,
                        price=price,
                        low_52=low_52,
                    )
                )

        return financial_context, warnings

    def validate_response_text(
        self,
        response_text: str,
        financial_context: dict | None,
    ) -> tuple[str, list[str]]:
        """Check the LLM response for hallucinated numbers.

        Extracts dollar amounts and percentages from the response text
        and cross-references against the financial context data.

        Args:
            response_text: LLM-generated response
            financial_context: Structured financial data for verification

        Returns:
            Tuple of (response_text, warnings)
        """
        warnings: list[str] = []

        if not financial_context:
            return response_text, warnings

        # Extract all dollar amounts from response
        dollar_pattern = r"\$[\d,]+\.?\d*"
        prices_in_response = re.findall(dollar_pattern, response_text)

        # Build a set of "known" values from financial context
        known_values = set()
        for _, data in financial_context.items():
            if not isinstance(data, dict):
                continue
            for field in [
                "current_price",
                "previous_close",
                "week_52_high",
                "week_52_low",
                "day_high",
                "day_low",
                "book_value",
            ]:
                val = data.get(field)
                if val is not None:
                    known_values.add(round(float(val), 2))

        # Check if response mentions prices not in our context
        for price_str in prices_in_response:
            try:
                price_val = float(price_str.replace("$", "").replace(",", ""))
                # Allow small rounding differences
                is_known = (
                    any(
                        abs(price_val - known) / max(known, 0.01) < 0.05
                        for known in known_values
                    )
                    if known_values
                    else True
                )

                if not is_known and price_val > 1.0:
                    warnings.append(
                        PromptLoader.load(
                            "system/notices/mismatched_price", price_str=price_str
                        )
                    )
            except ValueError:
                continue

        return response_text, warnings

    def estimate_confidence(
        self,
        has_financial_context: bool,
        has_citations: bool,
        citation_count: int,
        used_web_search: bool,
    ) -> float:
        """Estimate response confidence based on data sources.

        Args:
            has_financial_context: Whether structured financial data was used
            has_citations: Whether any citations were generated
            citation_count: Number of citations
            used_web_search: Whether web search was used as fallback

        Returns:
            Confidence score 0.0-1.0
        """
        confidence = 0.5  # Base confidence (LLM knowledge only)

        if has_financial_context:
            confidence += 0.3  # Strong boost for grounded data

        if has_citations:
            confidence += min(0.1 * citation_count, 0.2)  # Up to +0.2 for citations

        if used_web_search and not has_financial_context:
            confidence -= 0.1  # Slight penalty for web-only answers

        return round(min(max(confidence, 0.0), 1.0), 2)

    def postprocess(
        self,
        response_text: str,
        financial_context: dict | None = None,
        citations: list[dict] | None = None,
        used_web_search: bool = False,
    ) -> dict[str, Any]:
        """Run all postprocessing checks.

        Args:
            response_text: LLM-generated response
            financial_context: Structured financial data
            citations: List of citation dicts
            used_web_search: Whether web search was used

        Returns:
            Dict with confidence, warnings, and validated context
        """
        all_warnings = []

        # 1. Validate financial context data
        validated_context, context_warnings = self.validate_financial_context(
            financial_context
        )
        all_warnings.extend(context_warnings)

        # 2. Cross-reference response against context
        _, text_warnings = self.validate_response_text(response_text, financial_context)
        all_warnings.extend(text_warnings)

        # 3. Estimate confidence
        confidence = self.estimate_confidence(
            has_financial_context=financial_context is not None,
            has_citations=bool(citations),
            citation_count=len(citations) if citations else 0,
            used_web_search=used_web_search,
        )

        if all_warnings:
            logger.info(
                f"[POSTPROCESSOR] {len(all_warnings)} warning(s) generated, "
                f"confidence={confidence}"
            )

        return {
            "confidence": confidence,
            "warnings": all_warnings,
            "financial_context": validated_context,
        }

    def extract_citations_from_text(self, text: str) -> list[dict[str, str]]:
        """Extract markdown links as citations from text.

        Finds patterns like [Title](URL) and converts them to citation dicts.

        Args:
            text: Text to search for links

        Returns:
            List of citation dictionaries
        """
        citations = []
        # Match markdown links: [Title](URL)
        # Avoid matching images ![Alt](URL)
        link_pattern = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")

        matches = link_pattern.findall(text)
        for title, url in matches:
            # Basic validation to ensure it looks like a URL
            if url.startswith("http") or url.startswith("www"):
                citations.append(
                    {"source": "web", "title": title, "url": url, "data_type": "url"}
                )

        return citations

    def build_sources(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format citations into a standard UI-ready source format.

        Args:
            citations: List of raw citation dictionaries

        Returns:
            List of formatted source dictionaries
        """
        from datetime import (  # Local import to avoid top-level bloat if not needed
            datetime, timezone)

        sources = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for cit in citations:
            raw_source_type = cit.get("source", "web")
            source_type = raw_source_type
            readable_source = "Unknown"

            if raw_source_type == "yfinance":
                readable_source = "Yahoo Finance"
                source_type = "yfinance"
            elif raw_source_type in {"document", "article"}:
                readable_source = (
                    "Knowledge Base"
                    if raw_source_type == "document"
                    else "Research Article"
                )
                source_type = "vectordb"
            elif raw_source_type == "web":
                readable_source = "Web Search"
                source_type = "web"

            sources.append(
                {
                    "source": readable_source,
                    "source_type": source_type,
                    "ticker": cit.get("ticker"),
                    "data_type": cit.get("data_type", "unknown"),
                    "url": cit.get("url"),
                    "id": cit.get("ticker") or cit.get("title"),
                    "retrieved_at": cit.get("retrieved_at") or now_iso,
                    "confidence": cit.get("confidence") or cit.get("score") or 1.0,
                }
            )
        return sources

    def build_chart_config(self, tickers: list[str]) -> dict | None:
        """Build chart configuration for the UI based on identified tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Chart configuration dictionary or None if no tickers
        """
        if not tickers:
            return None

        primary_ticker = tickers[0]
        return {
            "type": "candlestick",
            "symbol": primary_ticker,
            "period": "1mo",
            "comparisons": tickers[1:] if len(tickers) > 1 else [],
            "settings": {"showVolume": True, "theme": "light"},
        }
