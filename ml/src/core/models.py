"""
Pydantic models for the Query Intelligence system.

All models use Pydantic v2 for validation, serialization, and dynamic fields.
No static enums - fully dynamic classification.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class YFinanceMapping(BaseModel):
    """Dynamic yFinance endpoint mapping."""

    endpoint: str | None = Field(
        None,
        description="yFinance endpoint (e.g., info, financials, history)",
    )
    fields: list[str] = Field(
        default_factory=list,
        description="Specific fields to extract from the endpoint",
    )
    time_range: str | None = Field(
        None,
        description="Time range for historical data (e.g., 1y, 5y, max)",
    )

    model_config = {"extra": "allow"}  # Allow dynamic fields from LLM


class ExpandedQuery(BaseModel):
    """A single dynamically generated query expansion."""

    purpose: str = Field(
        ...,
        description="Why this expansion is relevant to the user's query",
    )
    query: str = Field(
        ...,
        description="The expanded analytical query",
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Priority level (1=critical, 5=optional)",
    )
    data_sources: list[str] = Field(
        default_factory=lambda: ["yfinance"],
        description="Data sources needed for this expansion",
    )
    yfinance: YFinanceMapping | None = Field(
        default=None,
        description="yFinance data mapping (optional for educational queries)",
    )

    model_config = {"extra": "allow"}


class QueryEntities(BaseModel):
    """Dynamically extracted entities from any financial query."""

    company_names: list[str] = Field(
        default_factory=list,
        description="All company names mentioned in the query",
    )
    tickers: list[str] = Field(
        default_factory=list,
        description="Resolved stock ticker symbols",
    )
    asset_types: list[str] = Field(
        default_factory=list,
        description="Types of assets mentioned (equity, etf, index, etc.)",
    )
    geography: list[str] = Field(
        default_factory=list,
        description="Geographic regions or markets mentioned",
    )
    timeframes: list[str] = Field(
        default_factory=list,
        description="Time periods mentioned or inferred",
    )
    financial_metrics: list[str] = Field(
        default_factory=list,
        description="Financial metrics or indicators mentioned",
    )
    comparison_entities: list[str] = Field(
        default_factory=list,
        description="Entities being compared (for comparative queries)",
    )
    industries_sectors: list[str] = Field(
        default_factory=list,
        description="Industries or sectors mentioned",
    )

    @field_validator("tickers", mode="before")
    @classmethod
    def uppercase_tickers(cls, v):
        """Ensure all tickers are uppercase."""
        if isinstance(v, list):
            return [t.upper() if isinstance(t, str) else t for t in v]
        return v

    model_config = {"extra": "allow"}

    def has_tickers(self) -> bool:
        """Check if any tickers were identified."""
        return len(self.tickers) > 0

    def is_comparative(self) -> bool:
        """Check if this is a comparative query."""
        return len(self.tickers) > 1 or len(self.comparison_entities) > 0

    def primary_ticker(self) -> str | None:
        """Get the primary ticker if available."""
        return self.tickers[0] if self.tickers else None


class QueryExpansionResult(BaseModel):
    """
    Complete result of dynamic query analysis.

    No static categories - all classification is dynamic and contextual.
    """

    query_identifier: str = Field(
        ...,
        description="Unique identifier for this query",
    )
    original_query: str = Field(
        ...,
        description="The original user query",
    )
    intent: str = Field(
        ...,
        description="Dynamically classified intent (not limited to predefined list)",
    )
    intent_category: str | None = Field(
        None,
        description="Broad category if applicable (analysis, comparison, decision, info)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the analysis (0-1)",
    )
    entities: QueryEntities = Field(
        ...,
        description="All extracted entities",
    )
    core_question: str = Field(
        ...,
        description="Normalized, clear version of the user's question",
    )
    expanded_queries: list[ExpandedQuery] = Field(
        default_factory=list,
        description="Dynamically generated query expansions",
    )
    context_requirements: list[str] = Field(
        default_factory=list,
        description="Types of data/context needed to answer this query",
    )
    requires_real_time_data: bool = Field(
        default=True,
        description="Whether real-time data is needed",
    )
    requires_article_context: bool = Field(
        default=True,
        # Default True: safer to over-fetch articles than to miss relevant market news.
        # The LLM sets this to False only for pure numeric queries (price, ratios, etc.).
        description="Whether scraped article/news context is needed for this query",
    )
    is_safe: bool = Field(
        default=True,
        description="Whether the query is safe from prompt injection or malicious intent",
    )
    is_financial: bool = Field(
        default=True,
        description="Whether the query is within the financial domain",
    )
    refusal_message: str | None = Field(
        default=None,
        description="Specific refusal message if is_safe or is_financial is False",
    )
    reasoning: str = Field(
        default="",
        description="LLM's reasoning for this analysis",
    )
    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions",
    )

    model_config = {"extra": "allow"}

    def get_primary_ticker(self) -> str | None:
        """Get the first ticker if available."""
        ents: QueryEntities = self.entities
        return ents.primary_ticker()

    def get_all_tickers(self) -> list[str]:
        """Get all identified tickers."""
        ents: QueryEntities = self.entities
        return ents.tickers

    def is_comparative(self) -> bool:
        """Check if this is a comparative analysis."""
        ents: QueryEntities = self.entities
        return ents.is_comparative()

    def get_high_priority_queries(self, max_priority: int = 2) -> list[ExpandedQuery]:
        """Get only high-priority expanded queries."""
        return [eq for eq in self.expanded_queries if eq.priority <= max_priority]

    def get_queries_by_source(self, source: str = "yfinance") -> list[ExpandedQuery]:
        """Get queries that use a specific data source."""
        return [eq for eq in self.expanded_queries if source in eq.data_sources]

    def to_summary(self) -> dict[str, Any]:
        """Get a concise summary of the analysis."""
        ents: QueryEntities = self.entities
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "tickers": ents.tickers,
            "is_comparative": self.is_comparative(),
            "num_expansions": len(self.expanded_queries),
            "requires_real_time_data": self.requires_real_time_data,
        }


class TickerResolution(BaseModel):
    """Result of ticker resolution for a company name."""

    company_name: str = Field(..., description="Original company name")
    ticker: str | None = Field(None, description="Resolved ticker symbol")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    exchange: str | None = Field(None, description="Stock exchange")
    alternatives: list[str] = Field(
        default_factory=list,
        description="Alternative ticker suggestions",
    )
    validation_status: Literal["validated", "unvalidated", "failed"] = Field(
        default="unvalidated"
    )
    error: str | None = Field(None, description="Error message if resolution failed")

    model_config = {"extra": "allow"}


class FinancialContext(BaseModel):
    """
    Structured financial context for a single ticker.

    Used to build LLM context after data fetching.
    """

    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str | None = None

    # Price data
    current_price: float | None = None
    previous_close: float | None = None
    price_change: float | None = None
    price_change_pct: float | None = None

    # Valuation
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    book_value: float | None = None
    shares_outstanding: float | None = None
    earnings_per_share: float | None = None
    forward_eps: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    total_debt: float | None = None
    total_assets: float | None = None
    total_revenue: float | None = None
    enterprise_value: float | None = None
    ev_to_ebitda: float | None = None
    profit_margins: float | None = None
    currency: str | None = None

    # Company info
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None

    # Performance
    week_52_high: float | None = None
    week_52_low: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    avg_volume: int | None = None

    # Risk metrics
    beta: float | None = None

    # Income
    dividend_yield: float | None = None

    # Descriptions
    description: str | None = None

    # Summaries (formatted text)
    financials_summary: str | None = None
    performance_summary: str | None = None
    recommendations_summary: str | None = None

    # Metadata
    fetched_at: str | None = None
    data_quality: Literal["complete", "partial", "minimal"] = "minimal"

    model_config = {"extra": "allow"}

    def to_context_string(
        self,
        include_financials: bool = True,
        include_description: bool = True,
    ) -> str:
        """Convert to formatted context string for LLM.

        Args:
            include_financials: Whether to include detailed financial statements
            include_description: Whether to include longBusinessSummary (description field).
                Set to False for price/ratio/earnings queries to save 400-800 tokens.
                Set to True only for overview/about/general queries.
        """
        sections = [
            f"# {self.company_name or self.ticker} ({self.ticker})",
            "",
        ]

        if self.current_price is not None:
            sections.extend(self._build_price_section())

        if self.sector or self.industry:
            sections.extend(self._build_company_overview())

        if any([self.pe_ratio, self.forward_pe, self.peg_ratio, self.book_value]):
            sections.extend(self._build_valuation_metrics())

        if self.week_52_high or self.week_52_low:
            sections.extend(self._build_performance_section())

        if include_description and self.description:
            desc = (
                self.description[:500] + "..."
                if len(self.description) > 500
                else self.description
            )
            sections.extend(["## Business Description", desc, ""])

        if include_financials:
            sections.extend(self._build_summaries())

        if self.fetched_at:
            sections.append(f"_Data fetched: {self.fetched_at}_")

        return "\n".join(sections)

    def _get_currency_symbol(self) -> str:
        """Get symbol for currency code."""
        code = (self.currency or "USD").upper()
        return {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "INR": "₹",
            "JPY": "¥",
            "CNY": "¥",
            "AUD": "A$",
            "CAD": "C$",
        }.get(code, f"{code} ")

    def _build_price_section(self) -> list[str]:
        """Build the current market data section."""
        symbol = self._get_currency_symbol()
        lines = [
            "## Current Market Data",
            f"- **Current Price**: {symbol}{self.current_price:.2f}",
        ]

        if self.previous_close:
            lines.append(f"- **Previous Close**: {symbol}{self.previous_close:.2f}")

        if self.price_change_pct is not None:
            direction = "↑" if self.price_change_pct >= 0 else "↓"
            sign = "+" if self.price_change_pct >= 0 else "-"
            # Show absolute change too if possible
            if self.price_change:
                lines.append(
                    f"- **Day Change**: {direction} {symbol}{abs(self.price_change):.2f} "
                    f"({sign}{abs(self.price_change_pct):.2f}%)"
                )
            else:
                lines.append(
                    f"- **Day Change**: {direction} {sign}{abs(self.price_change_pct):.2f}%"
                )

        lines.append("")
        return lines

    def _build_company_overview(self) -> list[str]:
        """Build the company overview section."""
        lines = ["## Company Overview"]
        symbol = self._get_currency_symbol()
        if self.sector:
            lines.append(f"- **Sector**: {self.sector}")
        if self.industry:
            lines.append(f"- **Industry**: {self.industry}")
        if self.market_cap:
            lines.append(f"- **Market Cap**: {symbol}{self.market_cap:,.0f}")
        lines.append("")
        return lines

    def _build_valuation_metrics(self) -> list[str]:
        """Build the valuation metrics section."""
        lines = ["## Valuation Metrics"]
        currency = self.currency or "USD"
        # ... (rest is fine as it uses currency code suffix or no symbol) ...
        # Actually standard practice is symbol prefix for monetary values
        # But existing code uses {currency} suffix for some fields (line 383)
        # I'll leave valuation metrics as is for now to minimize diff,
        # or check line 380: currency = self.currency or "USD"

        metrics = [
            ("Book Value (per share)", self.book_value, f"{{:.2f}} {currency}"),
            ("P/B Ratio", self.price_to_book, "{:.2f}"),
            ("P/E Ratio", self.pe_ratio, "{:.2f}"),
            ("Forward P/E", self.forward_pe, "{:.2f}"),
            ("PEG Ratio", self.peg_ratio, "{:.2f}"),
            ("EPS (TTM)", self.earnings_per_share, f"{{:.2f}} {currency}"),
            ("Forward EPS", self.forward_eps, f"{{:.2f}} {currency}"),
            ("Shares Outstanding", self.shares_outstanding, "{:,.0f}"),
            ("Return on Equity", self.return_on_equity, "{:.2%}"),
            ("Return on Assets", self.return_on_assets, "{:.2%}"),
            ("Profit Margin", self.profit_margins, "{:.2%}"),
            ("Enterprise Value", self.enterprise_value, f"{{:,.0f}} {currency}"),
            ("EV/EBITDA", self.ev_to_ebitda, "{:.2f}"),
        ]

        for label, value, fmt in metrics:
            if value is not None:
                lines.append(f"- **{label}**: {fmt.format(value)}")
        lines.append("")
        return lines

    def _build_performance_section(self) -> list[str]:
        """Build the performance section."""
        lines = ["## Performance"]
        symbol = self._get_currency_symbol()
        if self.week_52_high and self.week_52_low:
            lines.append(
                f"- **52-Week Range**: {symbol}{self.week_52_low:.2f} - {symbol}{self.week_52_high:.2f}"
            )
        if self.beta:
            lines.append(f"- **Beta**: {self.beta:.2f}")
        if self.dividend_yield:
            lines.append(f"- **Dividend Yield**: {self.dividend_yield:.2%}")
        lines.append("")
        return lines

    def _build_summaries(self) -> list[str]:
        """Build the financial summaries section."""
        lines = []
        if self.financials_summary:
            lines.extend(["## Financial Statements", self.financials_summary, ""])
        if self.performance_summary:
            lines.extend(["## Performance Analysis", self.performance_summary, ""])
        if self.recommendations_summary:
            lines.extend(
                ["## Analyst Recommendations", self.recommendations_summary, ""]
            )
        return lines

    def is_complete(self) -> bool:
        """Check if we have comprehensive data."""
        required_fields = [
            self.current_price,
            self.sector,
            self.pe_ratio,
            self.market_cap,
        ]
        return all(field is not None for field in required_fields)


class MultiTickerContext(BaseModel):
    """Context for multiple tickers (comparative analysis)."""

    contexts: list[FinancialContext] = Field(default_factory=list)
    comparison_summary: str | None = None

    def to_context_string(self) -> str:
        """Build combined context for multiple tickers."""
        parts = []

        for i, ctx in enumerate(self.contexts, 1):
            parts.append(f"## Company {i}: {ctx.ticker}")
            parts.append(ctx.to_context_string(include_financials=False))
            parts.append("\n---\n")

        if self.comparison_summary:
            parts.extend(
                [
                    "## Comparative Analysis",
                    self.comparison_summary,
                ]
            )

        return "\n".join(parts)


class SearchResult(BaseModel):
    """Structured result from a vector search or RAG retrieval."""

    content: str = Field(..., description="The text content of the chunk")
    source_url: str | None = Field(None, description="Original source URL or file path")
    document_id: str | Any | None = Field(
        None, description="Unique identifier for the parent document"
    )
    chunk_index: int | None = Field(
        None, description="Index of this chunk within the document"
    )
    score: float = Field(
        default=0.0, description="Similarity score (closer to 1.0 is better)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional properties from the vector store"
    )

    def to_citation(self) -> dict[str, Any]:
        """Convert result to a standard citation format."""
        meta: dict[str, Any] = self.metadata
        return {
            "source": "document",
            "url": self.source_url,
            "title": meta.get("title") or self.source_url,
            "confidence": self.score,
            "data_type": "document",
        }


class SearchResponse(BaseModel):
    """Complete response from a RAG retrieval turn."""

    query: str = Field(..., description="The query used for search")
    results: list[SearchResult] = Field(
        default_factory=list, description="List of matched results"
    )
    total_matches: int = Field(default=0, description="Total number of matches found")
    processing_time_ms: float = Field(
        default=0.0, description="Time taken to retrieve results"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings encountered during search"
    )

    def get_combined_content(self) -> str:
        """Combine all result contents into a single string."""
        return "\n\n".join([r.content for r in self.results])

    def get_citations(self) -> list[dict[str, Any]]:
        """Get all results formatted as citations."""
        return [r.to_citation() for r in self.results]
