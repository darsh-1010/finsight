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

STRESS_SCENARIOS = {
    # 1. Historical Crashes
    "1987_Black_Monday": {
        "name": "1987 Black Monday",
        "category": "Historical Crashes",
        "start": "1987-10-19",
        "end": "1987-11-30",
        "description": "Single-day flash equity crash and aftermath",
        "type": "historical"
    },
    "1990_Nikkei_Collapse": {
        "name": "1990 Nikkei Collapse",
        "category": "Historical Crashes",
        "start": "1989-12-29",
        "end": "1992-08-18",
        "description": "Bursting of the Japanese asset price bubble",
        "type": "historical"
    },
    "2000_Dotcom_Bubble": {
        "name": "2000 Dot-com Bubble",
        "category": "Historical Crashes",
        "start": "2000-03-10",
        "end": "2002-10-09",
        "description": "Growth and technology stock bubble collapse",
        "type": "historical"
    },
    "2001_Sept_11": {
        "name": "Post-9/11 Shock",
        "category": "Historical Crashes",
        "start": "2001-09-10",
        "end": "2001-09-21",
        "description": "Market reaction to the September 11 terrorist attacks",
        "type": "historical"
    },
    "2008_Crash": {
        "name": "2008 Financial Crisis",
        "category": "Historical Crashes",
        "start": "2007-10-09",
        "end": "2009-03-09",
        "description": "Subprime mortgage collapse and banking crisis",
        "type": "historical"
    },
    "2010_Flash_Crash": {
        "name": "2010 Flash Crash",
        "category": "Historical Crashes",
        "start": "2010-05-06",
        "end": "2010-05-10",
        "description": "High-frequency algorithmic trading disruption",
        "type": "historical"
    },
    "2011_Euro_Debt": {
        "name": "2011 Eurozone Debt Crisis",
        "category": "Historical Crashes",
        "start": "2011-05-02",
        "end": "2011-10-04",
        "description": "Sovereign debt defaults and European banking panic",
        "type": "historical"
    },
    "2015_China_Crash": {
        "name": "2015 Chinese Equity Crash",
        "category": "Historical Crashes",
        "start": "2015-06-12",
        "end": "2015-08-26",
        "description": "Bursting of the leveraged mainland Chinese stock bubble",
        "type": "historical"
    },
    "2016_Brexit_Shock": {
        "name": "2016 Brexit Shock",
        "category": "Historical Crashes",
        "start": "2016-06-23",
        "end": "2016-06-27",
        "description": "Surprise UK EU referendum vote sell-off",
        "type": "historical"
    },
    "2018_Vol_Implosion": {
        "name": "2018 Volatility Implosion",
        "category": "Historical Crashes",
        "start": "2018-02-01",
        "end": "2018-02-09",
        "description": "Short volatility product unwind (Volpocalypse)",
        "type": "historical"
    },
    "2018_Growth_Selloff": {
        "name": "2018 Growth Sell-off",
        "category": "Historical Crashes",
        "start": "2018-10-01",
        "end": "2018-12-24",
        "description": "Fed rate hiking policy concerns and growth stock drop",
        "type": "historical"
    },
    "2020_COVID": {
        "name": "2020 COVID-19 Dip",
        "category": "Historical Crashes",
        "start": "2020-02-19",
        "end": "2020-03-23",
        "description": "Initial global pandemic lockdowns and market shock",
        "type": "historical"
    },
    "2022_Growth_Correction": {
        "name": "2022 Growth Correction",
        "category": "Historical Crashes",
        "start": "2022-01-03",
        "end": "2022-06-16",
        "description": "Post-COVID inflation surge and growth valuation drop",
        "type": "historical"
    },
    "2023_Banking_Panic": {
        "name": "2023 Regional Banking Panic",
        "category": "Historical Crashes",
        "start": "2023-03-08",
        "end": "2023-03-24",
        "description": "Silicon Valley Bank default and regional bank sell-off",
        "type": "historical"
    },

    # 2. Monetary & Inflation Shocks
    "1973_Stagflation": {
        "name": "1970s Oil Stagflation",
        "category": "Monetary & Inflation",
        "start": "1973-10-16",
        "end": "1974-12-31",
        "description": "High inflation, supply shocks, and stagnation",
        "type": "historical"
    },
    "1979_Volcker_Rates": {
        "name": "Volcker Rate Hikes",
        "category": "Monetary & Inflation",
        "start": "1979-10-01",
        "end": "1981-06-30",
        "description": "Double-digit Fed fund rates to curb runaway inflation",
        "type": "historical"
    },
    "1994_Bond_Massacre": {
        "name": "1994 Bond Massacre",
        "category": "Monetary & Inflation",
        "start": "1994-02-01",
        "end": "1994-11-30",
        "description": "Unscheduled rate hikes leading to bond price drops",
        "type": "historical"
    },
    "2013_Taper_Tantrum": {
        "name": "2013 Taper Tantrum",
        "category": "Monetary & Inflation",
        "start": "2013-05-22",
        "end": "2013-09-05",
        "description": "Panic over Fed signaling quantitative easing tapering",
        "type": "historical"
    },
    "2022_Fed_Tightening": {
        "name": "2022 Fed Rate Hike Cycle",
        "category": "Monetary & Inflation",
        "start": "2022-03-16",
        "end": "2022-12-30",
        "description": "Fastest interest rate hike cycle in decades",
        "type": "historical"
    },
    "2023_Fed_Pivot": {
        "name": "2023 Fed Pivot Speculation",
        "category": "Monetary & Inflation",
        "start": "2023-11-01",
        "end": "2024-01-31",
        "description": "Speculation over peak interest rates and future cuts",
        "type": "historical"
    },

    # 3. Geopolitical & Commodity Shocks
    "1973_OPEC_Embargo": {
        "name": "1973 OPEC Oil Embargo",
        "category": "Geopolitical & Commodities",
        "start": "1973-10-16",
        "end": "1974-03-18",
        "description": "Energy sector surge and shipping cost inflation",
        "type": "historical"
    },
    "1990_Gulf_War": {
        "name": "1990 Gulf War Shock",
        "category": "Geopolitical & Commodities",
        "start": "1990-08-02",
        "end": "1990-10-31",
        "description": "Iraq invasion of Kuwait and oil price spike",
        "type": "historical"
    },
    "2003_Iraq_Invasion": {
        "name": "2003 Iraq Invasion",
        "category": "Geopolitical & Commodities",
        "start": "2003-03-20",
        "end": "2003-04-30",
        "description": "War onset and defense sector outperformance",
        "type": "historical"
    },
    "2014_Oil_Collapse": {
        "name": "2014 Oil Price Collapse",
        "category": "Geopolitical & Commodities",
        "start": "2014-06-20",
        "end": "2015-01-31",
        "description": "US shale surge and OPEC price war, energy drop",
        "type": "historical"
    },
    "2018_Trade_War": {
        "name": "2018 US-China Trade War",
        "category": "Geopolitical & Commodities",
        "start": "2018-03-22",
        "end": "2018-12-24",
        "description": "Bilateral tariff escalation and supply chain friction",
        "type": "historical"
    },
    "2022_Ukraine_Invasion": {
        "name": "2022 Ukraine Invasion",
        "category": "Geopolitical & Commodities",
        "start": "2022-02-24",
        "end": "2022-04-30",
        "description": "Russia invasion onset and commodity spike",
        "type": "historical"
    },
    "2023_Gaza_Conflict": {
        "name": "2023 Israel-Gaza War",
        "category": "Geopolitical & Commodities",
        "start": "2023-10-07",
        "end": "2023-11-30",
        "description": "Gaza conflict escalation and regional risk premium",
        "type": "historical"
    },

    # 4. Currency & Sovereign Debt
    "1992_Black_Wednesday": {
        "name": "1992 Black Wednesday",
        "category": "Currency & Sovereign",
        "start": "1992-09-16",
        "end": "1992-09-30",
        "description": "GBP exits European Exchange Rate Mechanism",
        "type": "historical"
    },
    "1994_Tequila_Crisis": {
        "name": "1994 Mexican Peso Crisis",
        "category": "Currency & Sovereign",
        "start": "1994-12-20",
        "end": "1995-03-31",
        "description": "Mexican Peso devaluation and Tequila effect contagion",
        "type": "historical"
    },
    "1997_Asian_Contagion": {
        "name": "1997 Asian Financial Crisis",
        "category": "Currency & Sovereign",
        "start": "1997-07-02",
        "end": "1997-12-31",
        "description": "Thai Baht float trigger and East Asian devaluations",
        "type": "historical"
    },
    "1998_Russian_Default": {
        "name": "1998 Russian Ruble Crisis",
        "category": "Currency & Sovereign",
        "start": "1998-08-17",
        "end": "1998-10-15",
        "description": "Russian sovereign default and LTCM hedge fund collapse",
        "type": "historical"
    },
    "2001_Argentina_Default": {
        "name": "2001 Argentinian Debt Crisis",
        "category": "Currency & Sovereign",
        "start": "2001-11-30",
        "end": "2002-02-28",
        "description": "Corralito runs, peg removal, and sovereign default",
        "type": "historical"
    },
    "2012_Euro_Bailout": {
        "name": "2012 Greece PSI Default",
        "category": "Currency & Sovereign",
        "start": "2012-03-09",
        "end": "2012-05-31",
        "description": "Greek sovereign debt restructuring and default",
        "type": "historical"
    },
    "2015_Swiss_depeg": {
        "name": "2015 Swiss Franc Spike",
        "category": "Currency & Sovereign",
        "start": "2015-01-15",
        "end": "2015-01-22",
        "description": "SNB removes Euro peg, Swiss Franc surges 30%",
        "type": "historical"
    },
    "2014_Ruble_Crisis": {
        "name": "2014 Russian Ruble Crisis",
        "category": "Currency & Sovereign",
        "start": "2014-12-01",
        "end": "2014-12-31",
        "description": "Russian Ruble currency collapse from sanctions & oil",
        "type": "historical"
    },

    # 5. Hypothetical & Sector Shocks
    "Hypothetical_AI_Bubble_Burst": {
        "name": "AI Tech Bubble Burst",
        "category": "Hypothetical Shocks",
        "description": "High-growth AI/tech stocks experience severe correction while value stocks hold steady",
        "type": "synthetic",
        "shifts": {"TECH": -0.45, "DEFENSIVES": 0.05, "OTHER": -0.15}
    },
    "Hypothetical_Real_Estate_Crash": {
        "name": "Commercial Real Estate Crash",
        "category": "Hypothetical Shocks",
        "description": "Sovereign yield spike triggers commercial real estate valuations collapse",
        "type": "synthetic",
        "shifts": {"REITS": -0.35, "FINANCIALS": -0.15, "OTHER": -0.05}
    },
    "Hypothetical_Green_Transition": {
        "name": "Sudden Green Regulation Shock",
        "category": "Hypothetical Shocks",
        "description": "Aggressive carbon pricing impacts oil/gas assets while boosting renewables",
        "type": "synthetic",
        "shifts": {"RENEWABLES": 0.30, "ENERGY": -0.40, "OTHER": 0.0}
    },
    "Hypothetical_Supply_Chain_Freeze": {
        "name": "Global Supply Chain Freeze",
        "category": "Hypothetical Shocks",
        "description": "Geopolitical friction closes shipping lanes, spiking transport and goods inflation",
        "type": "synthetic",
        "shifts": {"INDUSTRIALS": -0.20, "TECH": -0.15, "GOLD": 0.10, "OTHER": -0.05}
    },
    "Hypothetical_Stagflation_Regime": {
        "name": "Modern Stagflation Regime",
        "category": "Hypothetical Shocks",
        "description": "Commodity shortages combine with wage spirals and high interest rates",
        "type": "synthetic",
        "shifts": {"COMMODITIES": 0.25, "EQUITIES": -0.20, "BONDS": -0.10, "OTHER": -0.05}
    }
}


def _classify_sector(ticker: str) -> str:
    ticker = ticker.upper().strip()
    tech_tickers = {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "NFLX", "META", "QQQ", "SMH"}
    reit_tickers = {"VNQ", "O", "AMT", "PLD", "CCI", "EQIX", "WY", "PSA"}
    energy_tickers = {"XLE", "XOM", "CVX", "COP", "SLB", "EOG", "PXD"}
    renewables_tickers = {"ICLN", "TAN", "ENPH", "FSLR", "NEE", "RUN"}
    commodity_tickers = {"GLD", "SLV", "USO", "UNG", "DBC", "PDBC", "IAU"}
    defensive_tickers = {"XLP", "XLV", "XLU", "PG", "JNJ", "KO", "PEP", "WMT", "LLY"}
    bond_tickers = {"BND", "TLT", "IEF", "SHY", "LQD", "HYG", "AGG"}
    
    if ticker in tech_tickers:
        return "TECH"
    elif ticker in reit_tickers:
        return "REITS"
    elif ticker in energy_tickers:
        return "ENERGY"
    elif ticker in renewables_tickers:
        return "RENEWABLES"
    elif ticker in commodity_tickers:
        return "COMMODITIES"
    elif ticker in defensive_tickers:
        return "DEFENSIVES"
    elif ticker in bond_tickers:
        return "BONDS"
    else:
        return "OTHER"


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
    def calculate_stress_test(portfolio: list[dict], scenarios: list[str] = None) -> dict:
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

        results = {}
        for name in scenarios:
            if name not in STRESS_SCENARIOS:
                continue

            dates = STRESS_SCENARIOS[name]

            if dates["type"] == "historical":
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

            elif dates["type"] == "synthetic":
                # Use a recent 1-year baseline for correlation/volatility modeling
                # from 2023-01-01 to 2023-12-31
                df = PortfolioService._fetch_historical_data(
                    tickers, "2023-01-01", "2023-12-31"
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

                # Apply synthetic shifts on top of baseline returns
                shifts = dates.get("shifts", {})
                num_days = len(daily_returns)

                port_daily_return = pd.Series(0.0, index=daily_returns.index)
                for ticker, weight in normalized_portfolio.items():
                    if ticker in daily_returns.columns:
                        sector = _classify_sector(ticker)
                        shift = shifts.get(sector, shifts.get("OTHER", 0.0))
                        
                        # Calculate daily shift multiplier factor
                        # e.g., (1 + shift) total return multiplier over baseline
                        factor = (1.0 + shift) ** (1.0 / num_days) if (1.0 + shift) > 0 else 0.0
                        
                        # Apply daily factor shift to baseline asset returns
                        asset_daily = (1 + daily_returns[ticker]) * factor - 1
                        port_daily_return += asset_daily * weight

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
