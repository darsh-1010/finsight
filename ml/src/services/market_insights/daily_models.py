"""Pydantic models for the Daily Market Insights compiler.

Defines structured daily analytical reports tailored specifically for subscription
tiers (Concise, Basic, Pro, and Institutional).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.services.market_insights.models import InsightCategory, InsightTopic

# ──────────────────────────────────────────────────────────────────────────────
# Standard Daily Summary Models
# ──────────────────────────────────────────────────────────────────────────────


class DailyStockHighlight(BaseModel):
    """Stock-specific highlight for the daily report."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    daily_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(..., description="Daily price change percentage")
    key_event: str = Field(
        ..., description="The main event that influenced this stock today"
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


class DailySummaryReport(BaseModel):
    """Synthesized daily report compiling all watchlist activity and news."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description="High-level narrative of today's market action (max 90 words)",
    )
    highlights: list[DailyStockHighlight] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed today (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ..., description="Actionable summary or key lesson for the user (max 50 words)"
    )
    user_id: str | None = Field(default=None, description="Requesting user identifier")


# ──────────────────────────────────────────────────────────────────────────────
# Tier-Specific Daily Summary Models (Tiers 1-4)
# ──────────────────────────────────────────────────────────────────────────────


class DailyStockHighlightTier1(BaseModel):
    """Stock-specific highlight for the daily report (Tier 1 - Concise)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    daily_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(..., description="Daily price change percentage")
    key_event: str = Field(
        ..., description="The main event that influenced this stock today"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Extremely concise analysis of this stock's performance. Format strictly as: "
            "a small paragraph of 1-2 sentences defining what is going on in the event, "
            "followed by pointwise bullet points covering key metrics and catalysts. (max 40 words)"
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


class DailySummaryReportTier1(BaseModel):
    """Synthesized daily report compiling all watchlist activity and news (Tier 1 - Concise)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description="High-level concise narrative of today's market action (max 90 words)",
    )
    highlights: list[DailyStockHighlightTier1] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed today (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable concise summary or key lesson for the user (max 50 words)",
    )


class DailyStockHighlightTier2(BaseModel):
    """Stock-specific highlight for the daily report (Tier 2 - Basic)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    daily_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(..., description="Daily price change percentage")
    key_event: str = Field(
        ..., description="The main event that influenced this stock today"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Clean, clear, and explanatory analysis of this stock's performance today. Format strictly as: "
            "a detailed paragraph of at least 2-3 sentences defining what is going on in the event, "
            "followed by pointwise bullet points covering key metrics and catalysts. (max 110 words)"
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


class DailySummaryReportTier2(BaseModel):
    """Synthesized daily report compiling all watchlist activity and news (Tier 2 - Basic)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description="Comprehensive high-level narrative of today's market action (max 160 words)",
    )
    highlights: list[DailyStockHighlightTier2] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed today (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable clear summary or key lesson for the user (max 110 words)",
    )


class DailyStockHighlightTier3(BaseModel):
    """Stock-specific highlight for the daily report (Tier 3 - Pro)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    daily_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(..., description="Daily price change percentage")
    key_event: str = Field(
        ..., description="The main event that influenced this stock today"
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


class DailySummaryReportTier3(BaseModel):
    """Synthesized daily report compiling all watchlist activity and news (Tier 3 - Pro)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description=(
            "Deep professional narrative of today's market action, "
            "including sector analysis and volatility notes (max 310 words)"
        ),
    )
    highlights: list[DailyStockHighlightTier3] = Field(
        default_factory=list, description="Stock-specific highlights"
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description="Key macroeconomic drivers observed today (e.g. CPI, Fed interest rates)",
    )
    key_takeaway: str = Field(
        ...,
        description="Actionable professional summary or strategic recommendation for the user (max 210 words)",
    )


class DailyStockHighlightTier4(BaseModel):
    """Stock-specific highlight for the daily report (Tier 4 - Institutional)."""

    ticker: str = Field(..., description="Stock ticker symbol (e.g. TSLA)")
    category: InsightCategory = Field(
        ..., description="One of the 6 high-level categories"
    )
    topic: InsightTopic = Field(..., description="One of the 30 strict topics")
    daily_trend: str = Field(
        ..., description="Overall trend: Bullish, Bearish, or Neutral"
    )
    price_change_pct: float = Field(..., description="Daily price change percentage")
    key_event: str = Field(
        ..., description="The main event that influenced this stock today"
    )
    verification_status: str = Field(
        "Verified",
        description="Fact-check status: Verified, Unverified, or Needs Review",
    )
    summary: str = Field(
        ...,
        description=(
            "Dense, institutional-grade, highly quantitative analysis of this stock's performance "
            "today. Focus heavily on valuation, earnings, relative strength, risk, and volatility. "
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


class DailySummaryReportTier4(BaseModel):
    """Synthesized daily report compiling all watchlist activity and news (Tier 4 - Institutional)."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_sentiment: str = Field(
        ...,
        description=(
            "Dense institutional-grade macro-economic analysis and quantitative market narrative "
            "(max 510 words)"
        ),
    )
    highlights: list[DailyStockHighlightTier4] = Field(
        default_factory=list,
        description="Stock-specific highlights",
    )
    macro_factors: list[str] = Field(
        default_factory=list,
        description=(
            "Key macroeconomic and monetary policy drivers observed today "
            "(e.g. CPI, Fed interest rates)"
        ),
    )
    key_takeaway: str = Field(
        ...,
        description="Highly strategic, risk-adjusted, institutional investment takeaway (max 310 words)",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Prompt Instructions
# ──────────────────────────────────────────────────────────────────────────────

TIER4_INSTRUCTIONS = (
    "You are an Elite Institutional Financial Analyst. Your goal is to synthesize the "
    "user's daily stock alerts with live yFinance news and calculated stock trends. Deliver "
    "a dense, institutional-grade, highly quantitative recap. Focus heavily on valuation "
    "metrics, earnings, absolute support/resistance price targets, macro-economic drivers, "
    "and risk profiles. Do not simplify terms; use professional financial language.\n"
    "Word constraints (strict, do not violate):\n"
    "- Stock highlight summary: Up to 510 words per stock. Format strictly as follows: "
    "First, write a detailed paragraph of at least 3-4 long, informative sentences defining the core event, "
    "explaining what is going on, trends, primary drivers, and broader market context. "
    "Then, provide pointwise bullet points covering the major parts of "
    "the insight (such as valuation metrics, "
    "earnings details, support/resistance price targets, and volatility/risk factors).\n"
    "- Overall sentiment: Up to 510 words (deep macro-economic and market-wide trend synthesis).\n"
    "- Key takeaway: Up to 310 words (dense strategic guidance, portfolio asset allocation and "
    "risk advice).\n\n"
    "PUSH NOTIFICATION REQUIREMENT:\n"
    "For each stock highlight, you MUST also generate a dynamic `alert_message` field "
    "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
    "'{Company Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
    "Keep the message under 110 characters total."
)

TIER3_INSTRUCTIONS = (
    "You are a Senior Wealth Management Portfolio Manager. Your goal is to synthesize daily "
    "stock watchlist alerts with live yFinance news and calculated trends. Deliver a highly "
    "detailed, professional-grade wealth summary. Explain the 'why' behind price movements, "
    "sector rotation, analyst ratings, and macro policies in professional but clear terms.\n"
    "Word constraints:\n"
    "- Stock highlight summary: Up to 260 words per stock. Format strictly as follows: "
    "First, write a detailed paragraph of at least 3 full, informative sentences defining the core event "
    "and explaining what is going on in detail (primary drivers, price catalysts). "
    "Then, provide pointwise bullet points covering the major parts of "
    "the insight (price drivers, catalysts, "
    "news details, volume).\n"
    "- Overall sentiment: Up to 310 words (comprehensive sector performance and market summary).\n"
    "- Key takeaway: Up to 210 words (actionable strategic wealth advice and portfolio "
    "recommendations).\n\n"
    "PUSH NOTIFICATION REQUIREMENT:\n"
    "For each stock highlight, you MUST also generate a dynamic `alert_message` field "
    "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
    "'{Company Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
    "Keep the message under 110 characters total."
)

TIER2_INSTRUCTIONS = (
    "You are a Personal Financial Advisor. Your goal is to synthesize the user's stock watchlist "
    "alerts with live yFinance news and trends. Provide a clean, explanatory, and clear narrative "
    "for an active retail investor. Avoid overwhelming terminology, but explain the core "
    "catalysts behind price and volume moves.\n"
    "Word constraints:\n"
    "- Stock highlight summary: Up to 110 words per stock. Format strictly as follows: "
    "First, write a detailed paragraph of at least 2-3 full sentences defining the core event "
    "and explaining what is going on. "
    "Then, provide pointwise bullet points covering the major parts of the insight "
    "(catalysts behind price/volume moves).\n"
    "- Overall sentiment: Up to 160 words (accessible summary of overall daily market behavior).\n"
    "- Key takeaway: Up to 110 words (actionable clear investment lesson or key takeaway).\n\n"
    "PUSH NOTIFICATION REQUIREMENT:\n"
    "For each stock highlight, you MUST also generate a dynamic `alert_message` field "
    "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
    "'{Company Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
    "Keep the message under 110 characters total."
)

TIER1_INSTRUCTIONS = (
    "You are a Concise Financial News Editor. Your goal is to synthesize the stock watchlist alerts "
    "with live yFinance news. Provide an extremely concise, high-level, bulleted daily summary "
    "for a busy user. Be brief and straight to the point.\n"
    "Word constraints (very strict):\n"
    "- Stock highlight summary: Maximum 40 words per stock. Format strictly as follows: "
    "First, write a concise paragraph of 1-2 sentences defining the core event. "
    "Then, provide concise pointwise bullet points covering the primary driver.\n"
    "- Overall sentiment: Maximum 90 words (brief market narrative).\n"
    "- Key takeaway: Maximum 50 words (short, punchy daily lesson).\n\n"
    "PUSH NOTIFICATION REQUIREMENT:\n"
    "For each stock highlight, you MUST also generate a dynamic `alert_message` field "
    "containing a premium, human-friendly, one-sentence push alert. Format strictly as:\n"
    "'{Company Name} [+/-X.X]% — [one-sentence fact-based insight from news]'\n"
    "Keep the message under 110 characters total."
)
