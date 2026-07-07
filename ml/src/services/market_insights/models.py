"""Pydantic models and enumerations for the Market Insights pipeline.

Defines the 6 categories and 30 strict topics the LLM maps events to,
plus the core data transfer objects used across all pipeline layers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# Event Type Enum
# ──────────────────────────────────────────────────────────────────────────────


class EventType(str, Enum):
    """Primitive market events detected by the trigger layer."""

    INTRADAY_DROP = "intraday_drop"  # >5% fall from the day's open
    INTRADAY_SURGE = "intraday_surge"  # >5% gain from the day's open
    WEEK_52_HIGH = "52_week_high"  # Price at/near 52-week ceiling
    WEEK_52_LOW = "52_week_low"  # Price at/near 52-week floor
    VOLUME_SPIKE = "volume_spike"  # Volume >2× the rolling average
    STANDARD_UPDATE = "standard_update"  # Fallback standard tracking update
    CORPORATE_ACTION = "corporate_action"  # Earnings dates, dividends, etc.
    ANALYST_EVENT = "analyst_event"  # Ratings changes, upgrades/downgrades
    NEWS_CATALYST = "news_catalyst"  # Macro, sector, risk news


# ──────────────────────────────────────────────────────────────────────────────
# 6 Categories & 30 Topics
# ──────────────────────────────────────────────────────────────────────────────


class InsightCategory(str, Enum):
    """High-level groupings for the 30 insight topics."""

    PRICE_ACTION = "Price Action"
    CORPORATE_EVENTS = "Corporate Events"
    MACROECONOMIC = "Macroeconomic"
    SECTOR_INDUSTRY = "Sector & Industry"
    ANALYST_ACTIVITY = "Analyst Activity"
    RISK_REGULATORY = "Risk & Regulatory"


class InsightTopic(str, Enum):
    """Strict taxonomy of 30 topics the LLM must classify events into."""

    # ── Price Action (1-5) ────────────────────────────────────────────────────
    INTRADAY_SURGE = "Intraday Surge"
    INTRADAY_DROP = "Intraday Drop"
    HIGH_52_WEEK = "52-Week High"
    LOW_52_WEEK = "52-Week Low"
    VOLUME_SPIKE = "Volume Spike"

    # ── Corporate Events (6-10) ───────────────────────────────────────────────
    EARNINGS_BEAT = "Earnings Beat"
    EARNINGS_MISS = "Earnings Miss"
    DIVIDEND_CHANGE = "Dividend Change"
    MA_ACTIVITY = "M&A Activity"
    EXECUTIVE_CHANGE = "Executive Change"

    # ── Macroeconomic (11-15) ─────────────────────────────────────────────────
    INTEREST_RATE_IMPACT = "Interest Rate Impact"
    INFLATION_DATA = "Inflation Data"
    GDP_REVISION = "GDP Revision"
    EMPLOYMENT_DATA = "Employment Data"
    TRADE_POLICY = "Trade Policy"

    # ── Sector & Industry (16-20) ─────────────────────────────────────────────
    SECTOR_ROTATION = "Sector Rotation"
    REGULATORY_APPROVAL = "Regulatory Approval"
    SUPPLY_CHAIN_DISRUPTION = "Supply Chain Disruption"
    COMMODITY_PRICE_MOVE = "Commodity Price Move"
    COMPETITIVE_LANDSCAPE_SHIFT = "Competitive Landscape Shift"

    # ── Analyst Activity (21-25) ──────────────────────────────────────────────
    RATING_UPGRADE = "Rating Upgrade"
    RATING_DOWNGRADE = "Rating Downgrade"
    PRICE_TARGET_RAISE = "Price Target Raise"
    PRICE_TARGET_CUT = "Price Target Cut"
    COVERAGE_INITIATION = "Coverage Initiation"

    # ── Risk & Regulatory (26-30) ─────────────────────────────────────────────
    SEC_INVESTIGATION = "SEC Investigation"
    REGULATORY_FINE = "Regulatory Fine"
    CREDIT_RATING_CHANGE = "Credit Rating Change"
    SHORT_INTEREST_SPIKE = "Short Interest Spike"
    GEOPOLITICAL_RISK = "Geopolitical Risk"


# ──────────────────────────────────────────────────────────────────────────────
# Data Transfer Objects
# ──────────────────────────────────────────────────────────────────────────────


class MarketEvent(BaseModel):
    """A primitive market event detected by the trigger layer."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. AAPL)")
    event_type: EventType = Field(..., description="Class of event detected")
    current_price: float = Field(..., description="Price at detection time")
    open_price: float | None = Field(None, description="Day open price if available")
    week_52_high: float | None = Field(None, description="52-week high watermark")
    week_52_low: float | None = Field(None, description="52-week low watermark")
    price_change_pct: float = Field(0.0, description="% change from open (signed)")
    volume: int | None = Field(None, description="Current trading volume")
    avg_volume: int | None = Field(None, description="30-day average volume")
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of detection",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary extra data from the data source",
    )


class InsightResult(BaseModel):
    """Fully classified insight produced by the LLM engine."""

    event: MarketEvent = Field(
        ..., description="Source event that triggered this insight"
    )
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM confidence score")
    summary: str = Field(..., description="One-sentence human-readable insight")
    context_insufficient: bool = Field(
        False,
        description="True when RAG returned no useful context; triggers web-search fallback",
    )
    fallback_used: bool = Field(
        False,
        description="True when Tavily web search was invoked as fallback",
    )


class AlertPayload(BaseModel):
    """Dispatchable alert ready for delivery to the user tier queue."""

    insight: InsightResult = Field(..., description="Classified insight")
    user_tier: int = Field(..., ge=0, le=5, description="Tier of the target user")
    user_id: str = Field(..., description="Unique user identifier")
    dispatched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when alert was dispatched",
    )
    is_immediate: bool = Field(
        False,
        description="True for Tier 3/4 live delivery; False for weekly summary",
    )


class ScanRequest(BaseModel):
    """Request body for manual scan trigger."""

    tickers: list[str] = Field(
        default_factory=list,
        description="Tickers to scan. Uses configured watchlist when empty.",
        max_length=50,
    )
    user_id: str = Field(..., description="Requesting user identifier")
    user_tier: int = Field(
        default=1, ge=0, le=5, description="User tier for dispatch routing"
    )


class ScanResponse(BaseModel):
    """Response from the scan endpoint."""

    scanned: int = Field(..., description="Number of tickers scanned")
    events_detected: int = Field(..., description="Raw market events found")
    alerts_dispatched: int = Field(
        ..., description="Alerts sent after dedup & tier routing"
    )
    insights: list[InsightResult] = Field(
        default_factory=list,
        description="Full classified insights returned for transparency",
    )


class WeeklyStockHighlight(BaseModel):
    """Stock-specific highlight for the weekly report."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    weekly_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(
        ..., description="Accumulated price change percentage for the week"
    )
    key_event: str = Field(
        ..., description="The main event that influenced this stock this week"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Analysis of this stock's performance. Format strictly as: a detailed paragraph "
            "of at least 3-4 sentences defining what is going on in the event, followed by "
            "pointwise bullet points covering key metrics and catalysts. (max 40 words)"
        ),
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Source URLs retrieved from Tavily to back up claims",
    )
    alert_message: str = Field(
        ...,
        description=(
            "A concise, insight-driven push notification message for this stock. "
            "Format: '[Company Name] [+/-pct]% — [one-line insight]. "
            "Max 110 characters."
        ),
    )
    insight_source: str = Field(
        ...,
        description="The source from which this insight was compiled (either 'yfinance' or 'websearch')",
    )


class WeeklySummaryReport(BaseModel):
    """Synthesized weekly report compiling all watchlist activity and news."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description="High-level narrative of the weekly market action (max 90 words)",
    )
    highlights: list[WeeklyStockHighlight] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed this week (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ..., description="Actionable summary or key lesson for the user (max 50 words)"
    )
    user_id: str | None = Field(default=None, description="Requesting user identifier")


# ──────────────────────────────────────────────────────────────────────────────
# Tier-Specific Weekly Summary Models (Tiers 1-4)
# ──────────────────────────────────────────────────────────────────────────────


class StockSummaryTier1(BaseModel):
    """Structured stock highlight summary for Tier 1 (Concise)."""

    paragraph: str = Field(
        ...,
        description=(
            "A qualitative paragraph of at least 2-3 sentences explaining what is "
            "going on in the event based on news. Do NOT include technical metrics "
            "(weekly change, RSI, volume ratio) in this paragraph. (max 80 words)"
        ),
    )
    weekly_change: str = Field(
        ...,
        description="The weekly price change percentage, e.g. '+9.14%' or '-5.40%'. Do not include brackets.",
    )
    rsi: str = Field(
        ...,
        description="The relative strength index value, e.g. '61.6' or '32.8'. Do not include brackets.",
    )
    volume_ratio: str = Field(
        ...,
        description="The volume ratio value, e.g. '1.75x' or '0.92x'. Do not include brackets.",
    )


class WeeklyStockHighlightTier1(BaseModel):
    """Stock-specific highlight for the weekly report (Tier 1 - Concise)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    weekly_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(
        ..., description="Accumulated price change percentage for the week"
    )
    key_event: str = Field(
        ..., description="The main event that influenced this stock this week"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: StockSummaryTier1 = Field(
        ...,
        description="Structured highlight summary separating qualitative narrative from technical metrics.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Source URLs retrieved from news to back up claims",
    )
    alert_message: str = Field(
        ...,
        description=(
            "A concise, insight-driven push notification message for this stock. "
            "Format: '[Company Name] [+/-pct]% — [one-line insight]. "
            "Max 110 characters."
        ),
    )
    insight_source: str = Field(
        ...,
        description="The source from which this insight was compiled (either 'yfinance' or 'websearch')",
    )


class WeeklySummaryReportTier1(BaseModel):
    """Synthesized weekly report compiling all watchlist activity and news (Tier 1 - Concise)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description=(
            "High-level narrative of the weekly market action in simple, "
            "clear terms (max 120 words)"
        ),
    )
    highlights: list[WeeklyStockHighlightTier1] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed this week (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable concise summary or key lesson in simple terms (max 80 words)",
    )


class StockSummaryTier2(BaseModel):
    """Structured stock highlight summary for Tier 2 (Basic)."""

    paragraph: str = Field(
        ...,
        description=(
            "A qualitative paragraph of at least 2-3 sentences explaining what is "
            "going on in the event based on news. Do NOT include technical metrics "
            "(weekly change, RSI, volume ratio) in this paragraph. (max 110 words)"
        ),
    )
    weekly_change: str = Field(
        ...,
        description="The weekly price change percentage, e.g. '+9.14%' or '-5.40%'. Do not include brackets.",
    )
    rsi: str = Field(
        ...,
        description="The relative strength index value, e.g. '61.6' or '32.8'. Do not include brackets.",
    )
    volume_ratio: str = Field(
        ...,
        description="The volume ratio value, e.g. '1.75x' or '0.92x'. Do not include brackets.",
    )


class WeeklyStockHighlightTier2(BaseModel):
    """Stock-specific highlight for the weekly report (Tier 2 - Basic)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    weekly_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(
        ..., description="Accumulated price change percentage for the week"
    )
    key_event: str = Field(
        ..., description="The main event that influenced this stock this week"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: StockSummaryTier2 = Field(
        ...,
        description="Structured highlight summary separating qualitative narrative from technical metrics.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Source URLs retrieved from news to back up claims",
    )
    alert_message: str = Field(
        ...,
        description=(
            "A concise, insight-driven push notification message for this stock. "
            "Format: '[Company Name] [+/-pct]% — [one-line insight]. "
            "Max 110 characters."
        ),
    )
    insight_source: str = Field(
        ...,
        description="The source from which this insight was compiled (either 'yfinance' or 'websearch')",
    )


class WeeklySummaryReportTier2(BaseModel):
    """Synthesized weekly report compiling all watchlist activity and news (Tier 2 - Basic)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description="Comprehensive high-level narrative of the weekly market action (max 160 words)",
    )
    highlights: list[WeeklyStockHighlightTier2] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed this week (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable clear summary or key lesson for the user (max 110 words)",
    )


class WeeklyStockHighlightTier3(BaseModel):
    """Stock-specific highlight for the weekly report (Tier 3 - Pro)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    weekly_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(
        ..., description="Accumulated price change percentage for the week"
    )
    key_event: str = Field(
        ..., description="The main event that influenced this stock this week"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Professional, deep-dive analysis of this stock's performance including volume dynamics "
            "and price action details. Format strictly as: a detailed paragraph of at least 3-4 sentences "
            "defining what is going on in the event, followed by pointwise bullet points covering key "
            "metrics and catalysts. (max 260 words)"
        ),
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Source URLs retrieved from news to back up claims",
    )
    alert_message: str = Field(
        ...,
        description=(
            "A concise, insight-driven push notification message for this stock. "
            "Format: '[Company Name] [+/-pct]% — [one-line insight]. "
            "Max 110 characters."
        ),
    )
    insight_source: str = Field(
        ...,
        description="The source from which this insight was compiled (either 'yfinance' or 'websearch')",
    )


class WeeklySummaryReportTier3(BaseModel):
    """Synthesized weekly report compiling all watchlist activity and news (Tier 3 - Pro)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description=(
            "Deep professional narrative of the weekly market action, "
            "including sector analysis and volatility notes (max 310 words)"
        ),
    )
    highlights: list[WeeklyStockHighlightTier3] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed this week (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable professional summary or strategic recommendation for the user (max 210 words)",
    )


class WeeklyStockHighlightTier4(BaseModel):
    """Stock-specific highlight for the weekly report (Tier 4 - Institutional)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    weekly_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(
        ..., description="Accumulated price change percentage for the week"
    )
    key_event: str = Field(
        ..., description="The main event that influenced this stock this week"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Dense, institutional-grade, highly quantitative analysis of this stock's performance. "
            "Focus heavily on valuation, earnings, relative strength, risk, and volatility. "
            "Format strictly as: a detailed paragraph of at least 3-4 sentences defining what is "
            "going on in the event, followed by pointwise bullet points covering key metrics and "
            "catalysts. (max 510 words)"
        ),
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Source URLs retrieved from news to back up claims",
    )
    alert_message: str = Field(
        ...,
        description=(
            "A concise, insight-driven push notification message for this stock. "
            "Format: '[Company Name] [+/-pct]% — [one-line insight]. "
            "Max 110 characters."
        ),
    )
    insight_source: str = Field(
        ...,
        description="The source from which this insight was compiled (either 'yfinance' or 'websearch')",
    )


class WeeklySummaryReportTier4(BaseModel):
    """Synthesized weekly report compiling all watchlist activity and news (Tier 4 - Institutional)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description=(
            "Dense institutional-grade macro-economic analysis and quantitative market narrative "
            "(max 510 words)"
        ),
    )
    highlights: list[WeeklyStockHighlightTier4] = Field(
        default_factory=list,
        description="Stock-specific highlights",
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description=(
            "Key macroeconomic and monetary policy drivers observed this week "
            "(e.g. CPI, Fed interest rates)"
        ),
    )
    key_takeaway: str = Field(
        ...,
        description="Highly strategic, risk-adjusted, institutional investment takeaway (max 310 words)",
    )
