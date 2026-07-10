from unittest.mock import patch

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
