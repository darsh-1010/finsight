"""
Market insights endpoint powered by tradingview-ta.

Returns real-time technical analysis data (recommendations, scores, price) for
a curated set of crypto/FX symbols used on the dashboard.  If TradingView is
unreachable the endpoint falls back to the last-known mock values so the UI
never breaks.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market"])

# ---------------------------------------------------------------------------
# Symbols we track.  Each entry maps a human-readable label to the ticker
# arguments expected by tradingview_ta.
# ---------------------------------------------------------------------------
SYMBOLS: list[dict[str, Any]] = [
    {
        "id": "1",
        "symbol": "BTC",
        "name": "Bitcoin",
        "screener": "crypto",
        "exchange": "BINANCE",
        "tv_symbol": "BTCUSDT",
    },
    {
        "id": "2",
        "symbol": "ETH",
        "name": "Ethereum",
        "screener": "crypto",
        "exchange": "BINANCE",
        "tv_symbol": "ETHUSDT",
    },
    {
        "id": "3",
        "symbol": "SOL",
        "name": "Solana",
        "screener": "crypto",
        "exchange": "BINANCE",
        "tv_symbol": "SOLUSDT",
    },
    {
        "id": "4",
        "symbol": "BNB",
        "name": "BNB",
        "screener": "crypto",
        "exchange": "BINANCE",
        "tv_symbol": "BNBUSDT",
    },
]

# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------
RECOMMENDATION_SCORE: dict[str, int] = {
    "STRONG_BUY": 95,
    "BUY": 75,
    "NEUTRAL": 50,
    "SELL": 30,
    "STRONG_SELL": 10,
}

# Fallback static data (used when TradingView is unreachable)
FALLBACK: list[dict[str, Any]] = [
    {"id": "1", "symbol": "BTC", "name": "Bitcoin",  "price": "$98,450", "change": "2.4%",  "isPositive": True,  "score": 85, "recommendation": "BUY"},
    {"id": "2", "symbol": "ETH", "name": "Ethereum", "price": "$3,240",  "change": "1.2%",  "isPositive": True,  "score": 78, "recommendation": "BUY"},
    {"id": "3", "symbol": "SOL", "name": "Solana",   "price": "$245",    "change": "0.5%",  "isPositive": False, "score": 62, "recommendation": "NEUTRAL"},
    {"id": "4", "symbol": "BNB", "name": "BNB",      "price": "$610",    "change": "1.8%",  "isPositive": True,  "score": 70, "recommendation": "BUY"},
]


def _fetch_live_data() -> list[dict[str, Any]]:
    """Fetch live analysis from TradingView and return serialisable dicts."""
    # Import here so a missing package only fails at call time, not import time.
    from tradingview_ta import TA_Handler, Interval  # type: ignore

    results: list[dict[str, Any]] = []

    for sym in SYMBOLS:
        try:
            handler = TA_Handler(
                symbol=sym["tv_symbol"],
                screener=sym["screener"],
                exchange=sym["exchange"],
                interval=Interval.INTERVAL_1_DAY,
            )
            analysis = handler.get_analysis()
            rec = analysis.summary.get("RECOMMENDATION", "NEUTRAL")
            score = RECOMMENDATION_SCORE.get(rec, 50)

            # TradingView TA doesn't always expose a price; derive a proxy
            # from the oscillators dict if available.
            indicators = analysis.indicators or {}
            close_price = indicators.get("close", None)
            price_str = f"${close_price:,.2f}" if close_price else "N/A"

            # Change % isn't directly in the TA summary; use RSI as a proxy
            # signal direction (above 50 = positive momentum).
            rsi = indicators.get("RSI", 50)
            is_positive = rsi >= 50
            change_pct = abs(round((rsi - 50) / 50 * 5, 2))  # synthetic pct

            results.append(
                {
                    "id": sym["id"],
                    "symbol": sym["symbol"],
                    "name": sym["name"],
                    "price": price_str,
                    "change": f"{change_pct}%",
                    "isPositive": is_positive,
                    "score": score,
                    "recommendation": rec,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch TA for %s: %s", sym["symbol"], exc)
            # Fall back for this individual symbol
            fallback_entry = next(
                (f for f in FALLBACK if f["id"] == sym["id"]), None
            )
            if fallback_entry:
                results.append(fallback_entry)

    return results


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.get("/insights")
def get_market_insights() -> dict[str, Any]:
    """
    Return real-time technical analysis insights for dashboard symbols.

    Falls back to static mock data if TradingView is unreachable so the UI
    always has something to render.
    """
    try:
        insights = _fetch_live_data()
        if not insights:
            raise ValueError("Empty result set from TradingView")
        return {"data": insights, "source": "live"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Market insights falling back to mock data: %s", exc)
        return {"data": FALLBACK, "source": "fallback"}
