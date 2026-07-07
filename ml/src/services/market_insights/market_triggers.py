"""Event Triggers Layer — yfinance-based market event detection.

Polls Yahoo Finance for a watchlist of tickers and emits MarketEvent
objects when any of these thresholds are breached:
  • Intraday move  >5 % from the day open (surge or drop)
  • 52-week high/low touch (±0.5 % tolerance band)
  • Volume spike   >2× the rolling 30-day average
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import yfinance as yf

from src.core.exceptions import YFinanceError
from src.services.market_insights.models import EventType, MarketEvent
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Detection Thresholds
# ──────────────────────────────────────────────────────────────────────────────

# Trigger an intraday event when price moves this far from the day open.
INTRADAY_MOVE_THRESHOLD = 0.05

# A volume reading above this multiple of the average is a spike.
VOLUME_SPIKE_MULTIPLIER = 2.0

# Price must be within this band of the 52-week extreme to trigger.
WEEK_52_TOLERANCE = 0.005


# ──────────────────────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────────────────────


class MarketTriggerService:
    """Scans a watchlist and detects primitive market events via yfinance.

    All I/O is performed inside a thread-pool executor so the service
    remains non-blocking inside an async event loop.
    """

    def __init__(self, max_concurrency: int = 5) -> None:
        """Initialise with an optional cap on parallel yfinance requests.

        Args:
            max_concurrency: Maximum simultaneous yfinance HTTP calls.
        """
        # Cap concurrent yfinance calls to avoid Yahoo Finance rate limits.
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def scan_watchlist(self, tickers: list[str]) -> list[MarketEvent]:
        """Concurrently scan all tickers and return every detected event.

        Args:
            tickers: Ticker symbols to scan (case-insensitive).

        Returns:
            Flat list of all MarketEvent objects detected in this run.
        """
        upper_tickers = [t.upper().strip() for t in tickers if t.strip()]
        tasks = [self._scan_one(ticker) for ticker in upper_tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events: list[MarketEvent] = []
        for ticker, result in zip(upper_tickers, results):
            if isinstance(result, Exception):
                logger.warning("[SCAN_SKIP] Ticker: %s | Reason: %s", ticker, result)
                continue
            events.extend(result)

        logger.info(
            "[SCAN_COMPLETE] Tickers: %d | Events: %d",
            len(upper_tickers),
            len(events),
        )
        return events

    async def _scan_one(self, ticker: str) -> list[MarketEvent]:
        """Fetch raw data and run all detection rules for one ticker.

        Args:
            ticker: Uppercase ticker symbol.

        Returns:
            List of events detected for this ticker (may be empty).
        """
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, self._fetch_ticker_data, ticker)
        return self._detect_events(ticker, raw)

    def _fetch_ticker_data(self, ticker: str) -> dict[str, Any]:
        """Synchronous yfinance fetch — runs inside an executor thread.

        Args:
            ticker: Uppercase ticker symbol.

        Returns:
            Dict with price, volume and 52-week fields.

        Raises:
            YFinanceError: When yfinance raises or returns empty data.
        """
        try:
            stock = yf.Ticker(ticker)
            info: dict[str, Any] = {}
            try:
                info = stock.info or {}
            except Exception as exc:
                logger.warning(
                    "[YFINANCE_INFO_WARN] Failed to fetch Ticker.info for %s: %s",
                    ticker,
                    exc,
                )

            price = info.get("currentPrice") or info.get("regularMarketPrice")
            open_price = info.get("open") or info.get("regularMarketOpen")
            week_52_high = info.get("fiftyTwoWeekHigh")
            week_52_low = info.get("fiftyTwoWeekLow")
            volume = info.get("volume")
            avg_volume = info.get("averageVolume")

            # Core fields recovery using fast_info
            if hasattr(stock, "fast_info"):
                try:
                    fi = stock.fast_info
                    if not price:
                        price = fi.get("lastPrice") or getattr(fi, "last_price", None)
                    if not open_price:
                        open_price = fi.get("open") or getattr(fi, "open", None)
                    if not week_52_high:
                        week_52_high = fi.get("yearHigh") or getattr(
                            fi, "year_high", None
                        )
                    if not week_52_low:
                        week_52_low = fi.get("yearLow") or getattr(fi, "year_low", None)
                    if not volume:
                        volume = fi.get("lastVolume") or getattr(
                            fi, "last_volume", None
                        )
                    if not avg_volume:
                        avg_volume = (
                            fi.get("threeMonthAverageVolume")
                            or getattr(fi, "three_month_average_volume", None)
                            or fi.get("tenDayAverageVolume")
                            or getattr(fi, "ten_day_average_volume", None)
                        )
                except Exception as exc:
                    logger.warning(
                        "[YFINANCE_FASTINFO_WARN] Failed to fetch Ticker.fast_info for %s: %s",
                        ticker,
                        exc,
                    )

            if not price:
                raise ValueError(f"No price data available for ticker {ticker}")

            # Analyst recommendations
            analyst_data = None
            try:
                recs = stock.recommendations
                if recs is not None and not recs.empty:
                    latest_rec = recs.iloc[-1]
                    rec_time = recs.index[-1]
                    if (
                        datetime.utcnow()
                        - rec_time.to_pydatetime().replace(tzinfo=None)
                    ).total_seconds() < 172800:
                        analyst_data = {
                            "firm": str(latest_rec.get("Firm") or ""),
                            "to_grade": str(latest_rec.get("To Grade") or ""),
                            "from_grade": str(latest_rec.get("From Grade") or ""),
                            "action": str(latest_rec.get("Action") or ""),
                        }
            except Exception as exc:
                logger.warning(
                    "[YFINANCE_RECS_WARN] Ticker: %s | Error: %s", ticker, exc
                )

            # Dividends
            recent_dividend = None
            try:
                divs = stock.dividends
                if divs is not None and not divs.empty:
                    latest_div_date = divs.index[-1]
                    if (
                        datetime.utcnow()
                        - latest_div_date.to_pydatetime().replace(tzinfo=None)
                    ).total_seconds() < 172800:
                        recent_dividend = float(divs.iloc[-1])
            except Exception as exc:
                logger.warning(
                    "[YFINANCE_DIV_WARN] Ticker: %s | Error: %s", ticker, exc
                )

            # News
            news_catalysts = []
            try:
                ticker_news = stock.news
                if ticker_news:
                    for article in ticker_news[:5]:
                        title = article.get("title", "")
                        publish_time = article.get("providerPublishTime")
                        if (
                            publish_time
                            and (datetime.utcnow().timestamp() - publish_time) < 86400
                        ):
                            title_lower = title.lower()
                            macro_keywords = [
                                "interest rate",
                                "inflation",
                                "fed ",
                                "cpi",
                                "gdp",
                                "employment",
                                "tariff",
                                "trade policy",
                            ]
                            risk_keywords = [
                                "sec ",
                                "investigation",
                                "regulatory fine",
                                "lawsuit",
                                "short interest",
                                "downgrade",
                                "credit rating",
                                "geopolitical",
                            ]
                            sector_keywords = [
                                "supply chain",
                                "disruption",
                                "competitive",
                                "market share",
                                "acquisition",
                                "merger",
                            ]

                            matched_type = None
                            if any(kw in title_lower for kw in macro_keywords):
                                matched_type = "macro"
                            elif any(kw in title_lower for kw in risk_keywords):
                                matched_type = "risk"
                            elif any(kw in title_lower for kw in sector_keywords):
                                matched_type = "sector"

                            if matched_type:
                                news_catalysts.append(
                                    {
                                        "title": title,
                                        "link": article.get("link", ""),
                                        "type": matched_type,
                                    }
                                )
            except Exception as exc:
                logger.warning(
                    "[YFINANCE_NEWS_WARN] Ticker: %s | Error: %s", ticker, exc
                )

            return {
                "price": price,
                "open": open_price,
                "week_52_high": week_52_high,
                "week_52_low": week_52_low,
                "volume": volume,
                "avg_volume": avg_volume,
                "analyst_data": analyst_data,
                "recent_dividend": recent_dividend,
                "news_catalysts": news_catalysts,
            }
        except (ValueError, TypeError, AttributeError, RuntimeError) as exc:
            raise YFinanceError(
                f"Fetch failed for {ticker}",
                details={"ticker": ticker, "error": str(exc)},
            ) from exc

    def _detect_events(self, ticker: str, data: dict[str, Any]) -> list[MarketEvent]:
        """Apply all detection rules and return matched events.

        Args:
            ticker: Uppercase ticker symbol.
            data: Raw dict from _fetch_ticker_data.

        Returns:
            List of matched MarketEvent objects.
        """
        current_price: float | None = data.get("price")
        if not current_price:
            logger.debug("[SKIP] Ticker: %s | Reason: no_price_data", ticker)
            return []

        events: list[MarketEvent] = []
        self._check_intraday_move(ticker, data, events)
        self._check_52_week(ticker, data, events)
        self._check_volume_spike(ticker, data, events)
        self._check_analyst_event(ticker, data, events)
        self._check_corporate_action(ticker, data, events)
        self._check_news_catalyst(ticker, data, events)

        # Fallback: if no extreme primitive triggers occur, always generate a STANDARD_UPDATE event
        if not events:
            events.append(_build_event(ticker, EventType.STANDARD_UPDATE, data))
            logger.info(
                "[EVENT_DETECTED] Ticker: %s | Type: standard_update | Price: %.2f",
                ticker,
                current_price,
            )

        return events

    def _check_intraday_move(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append a surge/drop event if the intraday threshold is breached."""
        current_price = data["price"]
        open_price = data.get("open")
        change_pct = _calc_change_pct(current_price, open_price)

        if abs(change_pct) < INTRADAY_MOVE_THRESHOLD:
            return
        event_type = (
            EventType.INTRADAY_SURGE if change_pct > 0 else EventType.INTRADAY_DROP
        )
        events.append(_build_event(ticker, event_type, data))
        logger.info(
            "[EVENT_DETECTED] Ticker: %s | Type: %s | Change: %.2f%%",
            ticker,
            event_type.value,
            change_pct * 100,
        )

    def _check_52_week(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append a 52-week high or low event when price touches the extreme."""
        current_price = data["price"]
        week_52_high: float | None = data.get("week_52_high")
        week_52_low: float | None = data.get("week_52_low")

        if week_52_high and current_price >= week_52_high * (1.0 - WEEK_52_TOLERANCE):
            events.append(_build_event(ticker, EventType.WEEK_52_HIGH, data))
            logger.info(
                "[EVENT_DETECTED] Ticker: %s | Type: 52_week_high | Price: %.2f",
                ticker,
                current_price,
            )

        if week_52_low and current_price <= week_52_low * (1.0 + WEEK_52_TOLERANCE):
            events.append(_build_event(ticker, EventType.WEEK_52_LOW, data))
            logger.info(
                "[EVENT_DETECTED] Ticker: %s | Type: 52_week_low | Price: %.2f",
                ticker,
                current_price,
            )

    def _check_volume_spike(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append a volume-spike event if volume exceeds the multiplier threshold."""
        volume: int | None = data.get("volume")
        avg_volume: int | None = data.get("avg_volume")

        if not volume or not avg_volume or avg_volume == 0:
            return
        if volume < avg_volume * VOLUME_SPIKE_MULTIPLIER:
            return

        events.append(_build_event(ticker, EventType.VOLUME_SPIKE, data))
        logger.info(
            "[EVENT_DETECTED] Ticker: %s | Type: volume_spike | Ratio: %.1fx",
            ticker,
            volume / avg_volume,
        )

    def _check_analyst_event(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append an analyst-event if recommendations are found."""
        analyst_data = data.get("analyst_data")
        if not analyst_data:
            return

        evt = _build_event(ticker, EventType.ANALYST_EVENT, data)
        evt.context = {"analyst_data": analyst_data}
        events.append(evt)
        logger.info(
            "[EVENT_DETECTED] Ticker: %s | Type: analyst_event | Firm: %s | Action: %s",
            ticker,
            analyst_data.get("firm"),
            analyst_data.get("action"),
        )

    def _check_corporate_action(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append a corporate-action event if dividends or calendar events are found."""
        div = data.get("recent_dividend")
        if not div:
            return

        evt = _build_event(ticker, EventType.CORPORATE_ACTION, data)
        evt.context = {"corporate_data": {"dividend": div}}
        events.append(evt)
        logger.info(
            "[EVENT_DETECTED] Ticker: %s | Type: corporate_action | Dividend: %.4f",
            ticker,
            div,
        )

    def _check_news_catalyst(
        self,
        ticker: str,
        data: dict[str, Any],
        events: list[MarketEvent],
    ) -> None:
        """Append a news-catalyst event if relevant news articles are found."""
        catalysts = data.get("news_catalysts")
        if not catalysts:
            return

        evt = _build_event(ticker, EventType.NEWS_CATALYST, data)
        evt.context = {"news_data": catalysts}
        events.append(evt)
        logger.info(
            "[EVENT_DETECTED] Ticker: %s | Type: news_catalyst | Count: %d",
            ticker,
            len(catalysts),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers (no self — pure functions)
# ──────────────────────────────────────────────────────────────────────────────


def _calc_change_pct(current_price: float, open_price: float | None) -> float:
    """Calculate signed percentage change from open to current price.

    Args:
        current_price: Latest price.
        open_price: Day open price; returns 0.0 if absent.

    Returns:
        Signed ratio in [−1, +∞); multiply by 100 for percentage.
    """
    if not open_price:
        return 0.0
    return (current_price - open_price) / open_price


def _build_event(
    ticker: str,
    event_type: EventType,
    data: dict[str, Any],
) -> MarketEvent:
    """Construct a MarketEvent from raw yfinance data.

    Args:
        ticker: Uppercase ticker symbol.
        event_type: Classified event type.
        data: Full raw dict from _fetch_ticker_data.

    Returns:
        Populated MarketEvent instance.
    """
    current_price = data["price"]
    open_price = data.get("open")
    change_pct = _calc_change_pct(current_price, open_price)

    return MarketEvent(
        ticker=ticker,
        event_type=event_type,
        current_price=current_price,
        open_price=open_price,
        week_52_high=data.get("week_52_high"),
        week_52_low=data.get("week_52_low"),
        price_change_pct=round(change_pct * 100, 4),
        volume=data.get("volume"),
        avg_volume=data.get("avg_volume"),
        detected_at=datetime.utcnow(),
    )
