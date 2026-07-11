"""
Tests for GET /api/v1/market/insights.

All TradingView network calls are mocked so this test suite runs fully offline.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

EXPECTED_KEYS = {"id", "symbol", "name", "price", "change", "isPositive", "score", "recommendation"}

MOCK_LIVE_DATA = [
    {
        "id": "1",
        "symbol": "BTC",
        "name": "Bitcoin",
        "price": "$60,000.00",
        "change": "1.5%",
        "isPositive": True,
        "score": 75,
        "recommendation": "BUY",
    },
    {
        "id": "2",
        "symbol": "ETH",
        "name": "Ethereum",
        "price": "$3,000.00",
        "change": "0.8%",
        "isPositive": True,
        "score": 65,
        "recommendation": "NEUTRAL",
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMarketInsights:
    """Integration tests for the /market/insights endpoint."""

    def test_market_insights_returns_200(self, client: TestClient):
        """Endpoint returns HTTP 200 regardless of TradingView availability."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        assert response.status_code == 200

    def test_market_insights_response_has_data_key(self, client: TestClient):
        """Response body must contain a 'data' list."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_market_insights_response_has_source_key(self, client: TestClient):
        """Response body must contain a 'source' field ('live' or 'fallback')."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        body = response.json()
        assert "source" in body
        assert body["source"] in {"live", "fallback"}

    def test_market_insights_live_source(self, client: TestClient):
        """When live data is available, source should be 'live'."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        assert response.json()["source"] == "live"

    def test_market_insights_fallback_on_error(self, client: TestClient):
        """When _fetch_live_data raises, endpoint falls back to static data with source='fallback'."""
        with patch("app.api.routes.market._fetch_live_data", side_effect=RuntimeError("TradingView down")):
            response = client.get("/api/v1/market/insights")
        body = response.json()
        assert response.status_code == 200
        assert body["source"] == "fallback"
        assert len(body["data"]) > 0

    def test_market_insights_fallback_on_empty_result(self, client: TestClient):
        """When _fetch_live_data returns empty list, endpoint falls back to static data."""
        with patch("app.api.routes.market._fetch_live_data", return_value=[]):
            response = client.get("/api/v1/market/insights")
        body = response.json()
        assert response.status_code == 200
        assert body["source"] == "fallback"

    def test_market_insights_item_structure(self, client: TestClient):
        """Each item in the response must contain all required keys."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        items = response.json()["data"]
        for item in items:
            missing = EXPECTED_KEYS - set(item.keys())
            assert not missing, f"Item missing keys: {missing} — item: {item}"

    def test_market_insights_score_range(self, client: TestClient):
        """Score values must be integers between 0 and 100."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        for item in response.json()["data"]:
            assert 0 <= item["score"] <= 100, f"Score out of range: {item['score']}"

    def test_market_insights_recommendation_values(self, client: TestClient):
        """Recommendation field must be one of the known values."""
        valid_recommendations = {"STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"}
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        for item in response.json()["data"]:
            assert item["recommendation"] in valid_recommendations, (
                f"Unexpected recommendation: {item['recommendation']}"
            )

    def test_market_insights_no_auth_required(self, client: TestClient):
        """Market insights must be public — no authentication required."""
        with patch("app.api.routes.market._fetch_live_data", return_value=MOCK_LIVE_DATA):
            response = client.get("/api/v1/market/insights")
        assert response.status_code != 401
        assert response.status_code != 403

    def test_fetch_live_data_success(self):
        """Test _fetch_live_data internal function successfully parses TradingView response."""
        from app.api.routes.market import _fetch_live_data
        from unittest.mock import MagicMock

        mock_analysis = MagicMock()
        mock_analysis.summary = {"RECOMMENDATION": "BUY"}
        mock_analysis.indicators = {"close": 50000.0, "RSI": 60}

        with patch("tradingview_ta.TA_Handler") as mock_handler:
            mock_handler.return_value.get_analysis.return_value = mock_analysis
            results = _fetch_live_data()

        assert len(results) == 4
        assert results[0]["symbol"] == "BTC"
        assert results[0]["price"] == "$50,000.00"
        assert results[0]["change"] == "1.0%"
        assert results[0]["isPositive"] is True
        assert results[0]["score"] == 75
        assert results[0]["recommendation"] == "BUY"

    def test_fetch_live_data_individual_fallback(self):
        """Test _fetch_live_data falls back to mock value for individual failed symbol."""
        from app.api.routes.market import _fetch_live_data

        with patch("tradingview_ta.TA_Handler") as mock_handler:
            mock_handler.return_value.get_analysis.side_effect = Exception("API offline")
            results = _fetch_live_data()

        assert len(results) == 4
        assert results[0]["symbol"] == "BTC"
        assert results[0]["price"] == "$98,450"  # fallback value

