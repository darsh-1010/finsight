from unittest.mock import MagicMock, patch

import pandas as pd

from app.services.portfolio_service import PortfolioService


@patch("yfinance.download")
def test_calculate_stress_test_success(mock_download):
    # Mock yfinance response
    dates = pd.date_range("2007-10-09", periods=3)
    # yfinance multi-index mock: columns are (Price Type, Ticker)
    columns = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Close", "MSFT")])
    mock_df = pd.DataFrame(
        [[100.0, 50.0], [90.0, 48.0], [95.0, 49.0]], index=dates, columns=columns
    )
    mock_download.return_value = mock_df

    portfolio = [{"ticker": "AAPL", "weight": 0.6}, {"ticker": "MSFT", "weight": 0.4}]
    result = PortfolioService.calculate_stress_test(portfolio)

    assert "2008_Crash" in result
    assert result["2008_Crash"]["status"] == "success"
    assert "return_pct" in result["2008_Crash"]


@patch("yfinance.download")
def test_get_7_day_performance(mock_download):
    dates = pd.date_range("2020-01-01", periods=2)
    columns = pd.MultiIndex.from_tuples([("Close", "AAPL")])
    mock_df = pd.DataFrame([[100.0], [105.0]], index=dates, columns=columns)
    mock_download.return_value = mock_df

    result = PortfolioService.get_7_day_performance(["AAPL"])
    assert "AAPL" in result
    assert result["AAPL"]["price"] == 105.0
    assert result["AAPL"]["change_pct"] == 5.0


def _mock_ticker_info(sectors: dict[str, str]):
    """Build a yf.Ticker(...) side_effect returning a fixed .info["sector"] per ticker."""

    def _make_ticker(symbol: str) -> MagicMock:
        ticker = MagicMock()
        ticker.info = {"sector": sectors.get(symbol)}
        return ticker

    return _make_ticker


@patch("app.services.portfolio_service.yf.Ticker")
def test_concentration_flags_single_oversized_position(mock_ticker_cls):
    mock_ticker_cls.side_effect = _mock_ticker_info(
        {"AAPL": "Technology", "MSFT": "Technology"}
    )
    portfolio = [{"ticker": "AAPL", "weight": 0.8}, {"ticker": "MSFT", "weight": 0.2}]

    result = PortfolioService.calculate_concentration(portfolio)

    assert result["risk_level"] == "concentrated"
    assert result["max_position"] == {"ticker": "AAPL", "weight": 0.8}
    assert {"ticker": "AAPL", "weight": 0.8} in result["flagged_positions"]
    assert result["hhi"] == 0.68  # 0.8^2 + 0.2^2


@patch("app.services.portfolio_service.yf.Ticker")
def test_concentration_diversified_portfolio_has_no_flags(mock_ticker_cls):
    # 10 equal-weighted (10% each), distinct-sector positions: at the single-position
    # threshold (not above it) and well under the sector threshold.
    sectors = {
        "AAPL": "Technology",
        "JNJ": "Healthcare",
        "JPM": "Financial Services",
        "XOM": "Energy",
        "PG": "Consumer Defensive",
        "NEE": "Utilities",
        "AMT": "Real Estate",
        "CAT": "Industrials",
        "VZ": "Communication Services",
        "NEM": "Basic Materials",
    }
    mock_ticker_cls.side_effect = _mock_ticker_info(sectors)
    portfolio = [{"ticker": t, "weight": 1.0 / len(sectors)} for t in sectors]

    result = PortfolioService.calculate_concentration(portfolio)

    assert result["risk_level"] == "diversified"
    assert result["flagged_positions"] == []
    assert result["flagged_sectors"] == []


@patch("app.services.portfolio_service.yf.Ticker")
def test_concentration_flags_oversized_sector_across_positions(mock_ticker_cls):
    # No single position exceeds 10%, but three same-sector positions together do (24%).
    mock_ticker_cls.side_effect = _mock_ticker_info(
        {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "JNJ": "Healthcare",
            "PG": "Consumer Defensive",
            "XOM": "Energy",
            "JPM": "Financial Services",
            "NEE": "Utilities",
            "AMT": "Real Estate",
            "CAT": "Industrials",
            "VZ": "Communication Services",
        }
    )
    portfolio = [
        {"ticker": "AAPL", "weight": 0.09},
        {"ticker": "MSFT", "weight": 0.09},
        {"ticker": "GOOGL", "weight": 0.09},
        {"ticker": "JNJ", "weight": 0.09125},
        {"ticker": "PG", "weight": 0.09125},
        {"ticker": "XOM", "weight": 0.09125},
        {"ticker": "JPM", "weight": 0.09125},
        {"ticker": "NEE", "weight": 0.09125},
        {"ticker": "AMT", "weight": 0.09125},
        {"ticker": "CAT", "weight": 0.09125},
        {"ticker": "VZ", "weight": 0.09125},
    ]

    result = PortfolioService.calculate_concentration(portfolio)

    flagged_sector_names = {s["sector"] for s in result["flagged_sectors"]}
    assert "Technology" in flagged_sector_names
    assert result["flagged_positions"] == []  # no single position crosses 10%


@patch("app.services.portfolio_service.yf.Ticker")
def test_concentration_falls_back_to_static_sector_map_on_yfinance_error(mock_ticker_cls):
    mock_ticker_cls.side_effect = RuntimeError("Yahoo Finance unavailable")
    portfolio = [{"ticker": "AAPL", "weight": 0.6}, {"ticker": "MSFT", "weight": 0.4}]

    result = PortfolioService.calculate_concentration(portfolio)

    # _classify_sector's static map buckets both AAPL and MSFT under "TECH".
    assert result["sector_breakdown"] == {"TECH": 1.0}


def test_concentration_rejects_invalid_weights():
    result = PortfolioService.calculate_concentration([{"ticker": "AAPL", "weight": 0.0}])
    assert "error" in result
