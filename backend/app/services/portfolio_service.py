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


STRESS_SCENARIOS = {
    # 1. Historical Crashes
    "1987_Black_Monday": {
        "name": "1987 Black Monday",
        "category": "Historical Crashes",
        "start": "1987-10-19",
        "end": "1987-11-30",
        "description": "Single-day flash equity crash and aftermath",
        "type": "historical",
    },
    "1990_Nikkei_Collapse": {
        "name": "1990 Nikkei Collapse",
        "category": "Historical Crashes",
        "start": "1989-12-29",
        "end": "1992-08-18",
        "description": "Bursting of the Japanese asset price bubble",
        "type": "historical",
    },
    "2000_Dotcom_Bubble": {
        "name": "2000 Dot-com Bubble",
        "category": "Historical Crashes",
        "start": "2000-03-10",
        "end": "2002-10-09",
        "description": "Growth and technology stock bubble collapse",
        "type": "historical",
    },
    "2001_Sept_11": {
        "name": "Post-9/11 Shock",
        "category": "Historical Crashes",
        "start": "2001-09-10",
        "end": "2001-09-21",
        "description": "Market reaction to the September 11 terrorist attacks",
        "type": "historical",
    },
    "2008_Crash": {
        "name": "2008 Financial Crisis",
        "category": "Historical Crashes",
        "start": "2007-10-09",
        "end": "2009-03-09",
        "description": "Subprime mortgage collapse and banking crisis",
        "type": "historical",
    },
    "2010_Flash_Crash": {
        "name": "2010 Flash Crash",
        "category": "Historical Crashes",
        "start": "2010-05-06",
        "end": "2010-05-10",
        "description": "High-frequency algorithmic trading disruption",
        "type": "historical",
    },
    "2011_Euro_Debt": {
        "name": "2011 Eurozone Debt Crisis",
        "category": "Historical Crashes",
        "start": "2011-05-02",
        "end": "2011-10-04",
        "description": "Sovereign debt defaults and European banking panic",
        "type": "historical",
    },
    "2015_China_Crash": {
        "name": "2015 Chinese Equity Crash",
        "category": "Historical Crashes",
        "start": "2015-06-12",
        "end": "2015-08-26",
        "description": "Bursting of the leveraged mainland Chinese stock bubble",
        "type": "historical",
    },
    "2016_Brexit_Shock": {
        "name": "2016 Brexit Shock",
        "category": "Historical Crashes",
        "start": "2016-06-23",
        "end": "2016-06-27",
        "description": "Surprise UK EU referendum vote sell-off",
        "type": "historical",
    },
    "2018_Vol_Implosion": {
        "name": "2018 Volatility Implosion",
        "category": "Historical Crashes",
        "start": "2018-02-01",
        "end": "2018-02-09",
        "description": "Short volatility product unwind (Volpocalypse)",
        "type": "historical",
    },
    "2018_Growth_Selloff": {
        "name": "2018 Growth Sell-off",
        "category": "Historical Crashes",
        "start": "2018-10-01",
        "end": "2018-12-24",
        "description": "Fed rate hiking policy concerns and growth stock drop",
        "type": "historical",
    },
    "2020_COVID": {
        "name": "2020 COVID-19 Dip",
        "category": "Historical Crashes",
        "start": "2020-02-19",
        "end": "2020-03-23",
        "description": "Initial global pandemic lockdowns and market shock",
        "type": "historical",
    },
    "2022_Growth_Correction": {
        "name": "2022 Growth Correction",
        "category": "Historical Crashes",
        "start": "2022-01-03",
        "end": "2022-06-16",
        "description": "Post-COVID inflation surge and growth valuation drop",
        "type": "historical",
    },
    "2023_Banking_Panic": {
        "name": "2023 Regional Banking Panic",
        "category": "Historical Crashes",
        "start": "2023-03-08",
        "end": "2023-03-24",
        "description": "Silicon Valley Bank default and regional bank sell-off",
        "type": "historical",
    },
    # 2. Monetary & Inflation Shocks
    "1973_Stagflation": {
        "name": "1970s Oil Stagflation",
        "category": "Monetary & Inflation",
        "start": "1973-10-16",
        "end": "1974-12-31",
        "description": "High inflation, supply shocks, and stagnation",
        "type": "historical",
    },
    "1979_Volcker_Rates": {
        "name": "Volcker Rate Hikes",
        "category": "Monetary & Inflation",
        "start": "1979-10-01",
        "end": "1981-06-30",
        "description": "Double-digit Fed fund rates to curb runaway inflation",
        "type": "historical",
    },
    "1994_Bond_Massacre": {
        "name": "1994 Bond Massacre",
        "category": "Monetary & Inflation",
        "start": "1994-02-01",
        "end": "1994-11-30",
        "description": "Unscheduled rate hikes leading to bond price drops",
        "type": "historical",
    },
    "2013_Taper_Tantrum": {
        "name": "2013 Taper Tantrum",
        "category": "Monetary & Inflation",
        "start": "2013-05-22",
        "end": "2013-09-05",
        "description": "Panic over Fed signaling quantitative easing tapering",
        "type": "historical",
    },
    "2022_Fed_Tightening": {
        "name": "2022 Fed Rate Hike Cycle",
        "category": "Monetary & Inflation",
        "start": "2022-03-16",
        "end": "2022-12-30",
        "description": "Fastest interest rate hike cycle in decades",
        "type": "historical",
    },
    "2023_Fed_Pivot": {
        "name": "2023 Fed Pivot Speculation",
        "category": "Monetary & Inflation",
        "start": "2023-11-01",
        "end": "2024-01-31",
        "description": "Speculation over peak interest rates and future cuts",
        "type": "historical",
    },
    # 3. Geopolitical & Commodity Shocks
    "1973_OPEC_Embargo": {
        "name": "1973 OPEC Oil Embargo",
        "category": "Geopolitical & Commodities",
        "start": "1973-10-16",
        "end": "1974-03-18",
        "description": "Energy sector surge and shipping cost inflation",
        "type": "historical",
    },
    "1990_Gulf_War": {
        "name": "1990 Gulf War Shock",
        "category": "Geopolitical & Commodities",
        "start": "1990-08-02",
        "end": "1990-10-31",
        "description": "Iraq invasion of Kuwait and oil price spike",
        "type": "historical",
    },
    "2003_Iraq_Invasion": {
        "name": "2003 Iraq Invasion",
        "category": "Geopolitical & Commodities",
        "start": "2003-03-20",
        "end": "2003-04-30",
        "description": "War onset and defense sector outperformance",
        "type": "historical",
    },
    "2014_Oil_Collapse": {
        "name": "2014 Oil Price Collapse",
        "category": "Geopolitical & Commodities",
        "start": "2014-06-20",
        "end": "2015-01-31",
        "description": "US shale surge and OPEC price war, energy drop",
        "type": "historical",
    },
    "2018_Trade_War": {
        "name": "2018 US-China Trade War",
        "category": "Geopolitical & Commodities",
        "start": "2018-03-22",
        "end": "2018-12-24",
        "description": "Bilateral tariff escalation and supply chain friction",
        "type": "historical",
    },
    "2022_Ukraine_Invasion": {
        "name": "2022 Ukraine Invasion",
        "category": "Geopolitical & Commodities",
        "start": "2022-02-24",
        "end": "2022-04-30",
        "description": "Russia invasion onset and commodity spike",
        "type": "historical",
    },
    "2023_Gaza_Conflict": {
        "name": "2023 Israel-Gaza War",
        "category": "Geopolitical & Commodities",
        "start": "2023-10-07",
        "end": "2023-11-30",
        "description": "Gaza conflict escalation and regional risk premium",
        "type": "historical",
    },
    # 4. Currency & Sovereign Debt
    "1992_Black_Wednesday": {
        "name": "1992 Black Wednesday",
        "category": "Currency & Sovereign",
        "start": "1992-09-16",
        "end": "1992-09-30",
        "description": "GBP exits European Exchange Rate Mechanism",
        "type": "historical",
    },
    "1994_Tequila_Crisis": {
        "name": "1994 Mexican Peso Crisis",
        "category": "Currency & Sovereign",
        "start": "1994-12-20",
        "end": "1995-03-31",
        "description": "Mexican Peso devaluation and Tequila effect contagion",
        "type": "historical",
    },
    "1997_Asian_Contagion": {
        "name": "1997 Asian Financial Crisis",
        "category": "Currency & Sovereign",
        "start": "1997-07-02",
        "end": "1997-12-31",
        "description": "Thai Baht float trigger and East Asian devaluations",
        "type": "historical",
    },
    "1998_Russian_Default": {
        "name": "1998 Russian Ruble Crisis",
        "category": "Currency & Sovereign",
        "start": "1998-08-17",
        "end": "1998-10-15",
        "description": "Russian sovereign default and LTCM hedge fund collapse",
        "type": "historical",
    },
    "2001_Argentina_Default": {
        "name": "2001 Argentinian Debt Crisis",
        "category": "Currency & Sovereign",
        "start": "2001-11-30",
        "end": "2002-02-28",
        "description": "Corralito runs, peg removal, and sovereign default",
        "type": "historical",
    },
    "2012_Euro_Bailout": {
        "name": "2012 Greece PSI Default",
        "category": "Currency & Sovereign",
        "start": "2012-03-09",
        "end": "2012-05-31",
        "description": "Greek sovereign debt restructuring and default",
        "type": "historical",
    },
    "2015_Swiss_depeg": {
        "name": "2015 Swiss Franc Spike",
        "category": "Currency & Sovereign",
        "start": "2015-01-15",
        "end": "2015-01-22",
        "description": "SNB removes Euro peg, Swiss Franc surges 30%",
        "type": "historical",
    },
    "2014_Ruble_Crisis": {
        "name": "2014 Russian Ruble Crisis",
        "category": "Currency & Sovereign",
        "start": "2014-12-01",
        "end": "2014-12-31",
        "description": "Russian Ruble currency collapse from sanctions & oil",
        "type": "historical",
    },
    # 5. Hypothetical & Sector Shocks
    "Hypothetical_AI_Bubble_Burst": {
        "name": "AI Tech Bubble Burst",
        "category": "Hypothetical Shocks",
        "description": "High-growth AI/tech stocks experience severe correction while value stocks hold steady",
        "type": "synthetic",
        "shifts": {"TECH": -0.45, "DEFENSIVES": 0.05, "OTHER": -0.15},
    },
    "Hypothetical_Real_Estate_Crash": {
        "name": "Commercial Real Estate Crash",
        "category": "Hypothetical Shocks",
        "description": "Sovereign yield spike triggers commercial real estate valuations collapse",
        "type": "synthetic",
        "shifts": {"REITS": -0.35, "FINANCIALS": -0.15, "OTHER": -0.05},
    },
    "Hypothetical_Green_Transition": {
        "name": "Sudden Green Regulation Shock",
        "category": "Hypothetical Shocks",
        "description": "Aggressive carbon pricing impacts oil/gas assets while boosting renewables",
        "type": "synthetic",
        "shifts": {"RENEWABLES": 0.30, "ENERGY": -0.40, "OTHER": 0.0},
    },
    "Hypothetical_Supply_Chain_Freeze": {
        "name": "Global Supply Chain Freeze",
        "category": "Hypothetical Shocks",
        "description": "Geopolitical friction closes shipping lanes, spiking transport and goods inflation",
        "type": "synthetic",
        "shifts": {"INDUSTRIALS": -0.20, "TECH": -0.15, "GOLD": 0.10, "OTHER": -0.05},
    },
    "Hypothetical_Stagflation_Regime": {
        "name": "Modern Stagflation Regime",
        "category": "Hypothetical Shocks",
        "description": "Commodity shortages combine with wage spirals and high interest rates",
        "type": "synthetic",
        "shifts": {
            "COMMODITIES": 0.25,
            "EQUITIES": -0.20,
            "BONDS": -0.10,
            "OTHER": -0.05,
        },
    },
}


# HHI bands: an equal-weighted N-stock portfolio has HHI = 1/N, so 0.15 ~ 7 holdings and
# 0.25 ~ 4 holdings - below that many effective holdings is thin diversification by common
# practitioner guidance.
HHI_DIVERSIFIED_MAX = 0.15
HHI_MODERATE_MAX = 0.25
# A single position above 10% of the portfolio, or a sector above 20%, is flagged as
# concentration risk per practitioner thresholds (Guardfolio, 2026).
SINGLE_POSITION_FLAG_THRESHOLD = 0.10
SECTOR_FLAG_THRESHOLD = 0.20


# Hardcoded ticker -> sector map, used as a fallback when live sector lookup fails.
_TICKER_SECTORS: dict[str, str] = {
    **dict.fromkeys(
        ("AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "NFLX", "META", "QQQ", "SMH"),
        "TECH",
    ),
    **dict.fromkeys(("VNQ", "O", "AMT", "PLD", "CCI", "EQIX", "WY", "PSA"), "REITS"),
    **dict.fromkeys(("XLE", "XOM", "CVX", "COP", "SLB", "EOG", "PXD"), "ENERGY"),
    **dict.fromkeys(("ICLN", "TAN", "ENPH", "FSLR", "NEE", "RUN"), "RENEWABLES"),
    **dict.fromkeys(("GLD", "SLV", "USO", "UNG", "DBC", "PDBC", "IAU"), "COMMODITIES"),
    **dict.fromkeys(
        ("XLP", "XLV", "XLU", "PG", "JNJ", "KO", "PEP", "WMT", "LLY"), "DEFENSIVES"
    ),
    **dict.fromkeys(("BND", "TLT", "IEF", "SHY", "LQD", "HYG", "AGG"), "BONDS"),
}


def _classify_sector(ticker: str) -> str:
    return _TICKER_SECTORS.get(ticker.upper().strip(), "OTHER")


def _resolve_sector(ticker: str) -> str:
    """Best-effort sector lookup: real Yahoo Finance data first, hardcoded map as fallback."""
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector") if info else None
        if sector:
            return sector
    except (ValueError, TypeError, AttributeError, RuntimeError, KeyError) as exc:
        logger.warning("[PORTFOLIO_SECTOR_FALLBACK] Ticker: %s | Error: %s", ticker, exc)
    return _classify_sector(ticker)


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
    def _no_data_result() -> dict:
        return {"return_pct": 0.0, "max_drawdown": 0.0, "status": "no_data"}

    @staticmethod
    def _summarize_performance(port_daily_return: pd.Series) -> dict:
        """Turn a daily return series into a rounded period return / max drawdown result."""
        cum_return = (1 + port_daily_return).cumprod()
        period_return = (
            float(cum_return.iloc[-1] - 1) if not cum_return.empty else 0.0
        )
        rolling_max = cum_return.cummax()
        drawdown = (cum_return - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
        return {
            "return_pct": round(period_return * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "status": "success",
        }

    @staticmethod
    def _weighted_daily_return(
        daily_returns: pd.DataFrame, normalized_portfolio: dict
    ) -> pd.Series:
        """Blend each ticker's daily returns by its normalized portfolio weight."""
        port_daily_return = pd.Series(0.0, index=daily_returns.index)
        for ticker, weight in normalized_portfolio.items():
            if ticker in daily_returns.columns:
                port_daily_return += daily_returns[ticker] * weight
        return port_daily_return

    @staticmethod
    def _weighted_synthetic_return(
        daily_returns: pd.DataFrame, normalized_portfolio: dict, shifts: dict
    ) -> pd.Series:
        """Apply a synthetic scenario's per-sector shift on top of baseline daily returns."""
        num_days = len(daily_returns)
        port_daily_return = pd.Series(0.0, index=daily_returns.index)
        for ticker, weight in normalized_portfolio.items():
            if ticker not in daily_returns.columns:
                continue
            sector = _classify_sector(ticker)
            shift = shifts.get(sector, shifts.get("OTHER", 0.0))
            # (1 + shift) total return multiplier over the baseline, spread daily
            factor = (
                (1.0 + shift) ** (1.0 / num_days) if (1.0 + shift) > 0 else 0.0
            )
            asset_daily = (1 + daily_returns[ticker]) * factor - 1
            port_daily_return += asset_daily * weight
        return port_daily_return

    @staticmethod
    def _run_scenario(
        name: str, tickers: list[str], normalized_portfolio: dict
    ) -> dict:
        """Run one stress scenario (historical replay or synthetic shift) end to end."""
        dates = STRESS_SCENARIOS[name]
        if dates["type"] == "historical":
            df = PortfolioService._fetch_historical_data(
                tickers, dates["start"], dates["end"]
            )
        else:
            # Synthetic scenarios shift a recent 1-year baseline (2023) by sector.
            df = PortfolioService._fetch_historical_data(
                tickers, "2023-01-01", "2023-12-31"
            )

        daily_returns = df.pct_change().dropna() if not df.empty else df
        if daily_returns.empty:
            return PortfolioService._no_data_result()

        if dates["type"] == "historical":
            port_daily_return = PortfolioService._weighted_daily_return(
                daily_returns, normalized_portfolio
            )
        else:
            port_daily_return = PortfolioService._weighted_synthetic_return(
                daily_returns, normalized_portfolio, dates.get("shifts", {})
            )
        return PortfolioService._summarize_performance(port_daily_return)

    @staticmethod
    def calculate_stress_test(
        portfolio: list[dict], scenarios: list[str] = None
    ) -> dict:
        """
        Calculate stress test performance for selected historical and synthetic crises.
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

        # Fallback to defaults to support tests and simple UI paths
        if not scenarios:
            scenarios = ["2008_Crash", "2020_COVID"]

        return {
            name: PortfolioService._run_scenario(name, tickers, normalized_portfolio)
            for name in scenarios
            if name in STRESS_SCENARIOS
        }

    @staticmethod
    def calculate_concentration(portfolio: list[dict]) -> dict:
        """
        Score a portfolio's concentration risk: single-position and sector exposure,
        plus a Herfindahl-Hirschman Index (HHI) summary score.
        Expects a list of dicts: [{"ticker": "AAPL", "weight": 0.6}, ...]
        """
        total_weight = sum(asset.get("weight", 0.0) for asset in portfolio)
        if total_weight <= 0:
            return {"error": "Invalid weights, must sum to > 0"}

        normalized = {
            asset["ticker"].upper(): asset["weight"] / total_weight
            for asset in portfolio
            if asset.get("ticker") and asset.get("weight")
        }
        if not normalized:
            return {"error": "No valid tickers provided"}

        hhi = sum(weight**2 for weight in normalized.values())
        if hhi < HHI_DIVERSIFIED_MAX:
            risk_level = "diversified"
        elif hhi < HHI_MODERATE_MAX:
            risk_level = "moderate"
        else:
            risk_level = "concentrated"

        max_ticker, max_weight = max(normalized.items(), key=lambda item: item[1])
        # Round before comparing to the threshold: normalizing by total_weight (itself a
        # float sum) can push an exact-at-threshold position a hair above it in floating
        # point (e.g. sum([0.1] * 10) is 1.0 on Python 3.12 but 0.9999999999999999 on
        # 3.11), which would spuriously flag it. 4dp is well below the 1e-4 threshold
        # granularity we display anyway.
        flagged_positions = [
            {"ticker": ticker, "weight": round(weight, 4)}
            for ticker, weight in normalized.items()
            if round(weight, 4) > SINGLE_POSITION_FLAG_THRESHOLD
        ]

        sector_breakdown: dict[str, float] = {}
        for ticker, weight in normalized.items():
            sector = _resolve_sector(ticker)
            sector_breakdown[sector] = sector_breakdown.get(sector, 0.0) + weight

        flagged_sectors = [
            {"sector": sector, "weight": round(weight, 4)}
            for sector, weight in sector_breakdown.items()
            if round(weight, 4) > SECTOR_FLAG_THRESHOLD
        ]

        return {
            "hhi": round(hhi, 4),
            "risk_level": risk_level,
            "max_position": {"ticker": max_ticker, "weight": round(max_weight, 4)},
            "flagged_positions": flagged_positions,
            "sector_breakdown": {sector: round(w, 4) for sector, w in sector_breakdown.items()},
            "flagged_sectors": flagged_sectors,
        }

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
