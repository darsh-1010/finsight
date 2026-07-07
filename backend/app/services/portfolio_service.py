"""
PortfolioService
================
Provides logic for the Sandbox Portfolio Stress-Tester and weekly performance metrics.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class PortfolioService:
    @staticmethod
    def _fetch_historical_data(
        tickers: list[str], start: str, end: str
    ) -> pd.DataFrame:
        """Fetch historical close prices for a list of tickers using yfinance."""
        if not tickers:
            return pd.DataFrame()

        try:
            # Download data quietly
            data = yf.download(tickers, start=start, end=end, progress=False)
            if data.empty:
                return pd.DataFrame()

            # Handle multi-index columns vs single-index depending on number of tickers
            if isinstance(data.columns, pd.MultiIndex):
                if "Close" in data.columns.get_level_values(0):
                    close_prices = data["Close"]
                else:
                    return pd.DataFrame()
            else:
                # If only one ticker is requested, it returns a single level DF where 'Close' is a column
                close_prices = pd.DataFrame({tickers[0]: data["Close"]})

            # Forward fill to handle missing daily data, then drop any remaining NaNs
            return close_prices.ffill().dropna()

        except Exception as exc:
            logger.error("[PORTFOLIO_FETCH_FAIL] Failed to fetch data: %s", exc)
            return pd.DataFrame()

    @staticmethod
    def calculate_stress_test(portfolio: list[dict]) -> dict:
        """
        Calculate stress test performance for predefined historical crises.
        Expects a list of dicts: [{"ticker": "AAPL", "weight": 0.6}, ...]
        """
        total_weight = sum(asset.get("weight", 0.0) for asset in portfolio)
        if total_weight <= 0:
            return {"error": "Invalid weights, must sum to > 0"}

        normalized_portfolio = {
            asset["ticker"].upper(): asset["weight"] / total_weight
            for asset in portfolio
            if asset.get("ticker") and asset.get("weight")
        }
        tickers = list(normalized_portfolio.keys())
        if not tickers:
            return {"error": "No valid tickers provided"}

        crises = {
            "2008_Crash": {"start": "2007-10-09", "end": "2009-03-09"},
            "2020_COVID": {"start": "2020-02-19", "end": "2020-03-23"},
        }

        results = {}
        for name, dates in crises.items():
            df = PortfolioService._fetch_historical_data(
                tickers, dates["start"], dates["end"]
            )
            if df.empty:
                results[name] = {
                    "return_pct": 0.0,
                    "max_drawdown": 0.0,
                    "status": "no_data",
                }
                continue

            daily_returns = df.pct_change().dropna()
            if daily_returns.empty:
                results[name] = {
                    "return_pct": 0.0,
                    "max_drawdown": 0.0,
                    "status": "no_data",
                }
                continue

            # Calculate daily weighted return for the portfolio
            port_daily_return = pd.Series(0.0, index=daily_returns.index)
            for ticker, weight in normalized_portfolio.items():
                if ticker in daily_returns.columns:
                    port_daily_return += daily_returns[ticker] * weight

            # Cumulative performance
            cum_return = (1 + port_daily_return).cumprod()

            period_return = (
                float(cum_return.iloc[-1] - 1) if not cum_return.empty else 0.0
            )
            rolling_max = cum_return.cummax()
            drawdown = (cum_return - rolling_max) / rolling_max
            max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

            results[name] = {
                "return_pct": round(period_return * 100, 2),
                "max_drawdown": round(max_drawdown * 100, 2),
                "status": "success",
            }

        return results

    @staticmethod
    def get_7_day_performance(tickers: list[str]) -> dict:
        """Fetch 7-day performance for email briefings."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(
            days=10
        )  # 10 calendar days to capture 7 trading days
        df = PortfolioService._fetch_historical_data(
            tickers, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        )

        perf = {}
        if df.empty:
            return perf

        for ticker in tickers:
            if ticker in df.columns:
                series = df[ticker].dropna()
                if len(series) >= 2:
                    start_price = float(series.iloc[0])
                    end_price = float(series.iloc[-1])
                    pct_change = ((end_price - start_price) / start_price) * 100
                    perf[ticker] = {
                        "price": round(end_price, 2),
                        "change_pct": round(pct_change, 2),
                    }
        return perf
