"""
Tests for portfolio stress-test endpoints.

  GET  /api/v1/portfolio/stress-test/scenarios
  POST /api/v1/portfolio/stress-test

yfinance calls are mocked — tests run fully offline.
"""

from unittest.mock import patch

import pytest


# ── Sample portfolio payload ──────────────────────────────────────────────────

VALID_PORTFOLIO = [{"ticker": "AAPL", "weight": 0.6}, {"ticker": "MSFT", "weight": 0.4}]

SINGLE_ASSET_PORTFOLIO = [{"ticker": "AAPL", "weight": 1.0}]

# Mock result returned by PortfolioService.calculate_stress_test
MOCK_STRESS_RESULT = {
    "2008_financial_crisis": {
        "return_pct": -38.5,
        "max_drawdown": -55.2,
        "status": "computed",
    }
}


# ── Scenario Listing ──────────────────────────────────────────────────────────

class TestGetStressScenarios:
    """Tests for GET /api/v1/portfolio/stress-test/scenarios."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated request must be rejected."""
        response = client.get("/api/v1/portfolio/stress-test/scenarios")
        assert response.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        """Authenticated user gets the list of scenarios."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/portfolio/stress-test/scenarios")
        assert response.status_code == 200

    def test_scenarios_is_a_list(self, auth_client):
        """Response body must be a JSON array."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/portfolio/stress-test/scenarios")
        assert isinstance(response.json(), list)

    def test_scenarios_non_empty(self, auth_client):
        """At least one scenario must be returned (seeded in source code)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/portfolio/stress-test/scenarios")
        assert len(response.json()) > 0

    def test_scenario_item_has_required_keys(self, auth_client):
        """Each scenario must have id, name, category, description, type."""
        required = {"id", "name", "category", "description", "type"}
        test_client, _ = auth_client
        response = test_client.get("/api/v1/portfolio/stress-test/scenarios")
        for scenario in response.json():
            missing = required - set(scenario.keys())
            assert not missing, f"Scenario missing keys: {missing}"


# ── Stress Test Execution ─────────────────────────────────────────────────────

class TestRunStressTest:
    """Tests for POST /api/v1/portfolio/stress-test."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated request must be rejected."""
        payload = {"portfolio": VALID_PORTFOLIO}
        response = client.post("/api/v1/portfolio/stress-test", json=payload)
        assert response.status_code == 401

    def test_valid_portfolio_returns_200(self, auth_client):
        """Valid authenticated request returns 200 with crisis results."""
        test_client, _ = auth_client
        with patch(
            "app.services.portfolio_service.PortfolioService.calculate_stress_test",
            return_value=MOCK_STRESS_RESULT,
        ):
            response = test_client.post(
                "/api/v1/portfolio/stress-test",
                json={"portfolio": VALID_PORTFOLIO},
            )
        assert response.status_code == 200

    def test_response_has_crises_key(self, auth_client):
        """Response body must contain the 'crises' key."""
        test_client, _ = auth_client
        with patch(
            "app.services.portfolio_service.PortfolioService.calculate_stress_test",
            return_value=MOCK_STRESS_RESULT,
        ):
            response = test_client.post(
                "/api/v1/portfolio/stress-test",
                json={"portfolio": SINGLE_ASSET_PORTFOLIO},
            )
        assert "crises" in response.json()

    def test_empty_portfolio_returns_422(self, auth_client):
        """An empty portfolio array must fail Pydantic validation (422)."""
        test_client, _ = auth_client
        response = test_client.post(
            "/api/v1/portfolio/stress-test",
            json={"portfolio": []},
        )
        assert response.status_code == 422

    def test_missing_portfolio_key_returns_422(self, auth_client):
        """Request without 'portfolio' key must return 422."""
        test_client, _ = auth_client
        response = test_client.post("/api/v1/portfolio/stress-test", json={})
        assert response.status_code == 422

    def test_negative_weight_returns_422(self, auth_client):
        """Negative weight values must be rejected by validation."""
        test_client, _ = auth_client
        response = test_client.post(
            "/api/v1/portfolio/stress-test",
            json={"portfolio": [{"ticker": "AAPL", "weight": -0.5}]},
        )
        # FastAPI passes through — service may return error or 400
        assert response.status_code in {400, 422}

    def test_service_error_propagated_as_400(self, auth_client):
        """When PortfolioService returns an error dict, endpoint raises HTTP 400."""
        test_client, _ = auth_client
        with patch(
            "app.services.portfolio_service.PortfolioService.calculate_stress_test",
            return_value={"error": "Could not fetch ticker data"},
        ):
            response = test_client.post(
                "/api/v1/portfolio/stress-test",
                json={"portfolio": SINGLE_ASSET_PORTFOLIO},
            )
        assert response.status_code == 400

    def test_scenarios_filter_is_optional(self, auth_client):
        """Request without 'scenarios' key should still succeed."""
        test_client, _ = auth_client
        with patch(
            "app.services.portfolio_service.PortfolioService.calculate_stress_test",
            return_value=MOCK_STRESS_RESULT,
        ):
            response = test_client.post(
                "/api/v1/portfolio/stress-test",
                json={"portfolio": SINGLE_ASSET_PORTFOLIO},
            )
        assert response.status_code == 200

    def test_scenarios_filter_accepted(self, auth_client):
        """Request with a specific scenarios list should be accepted."""
        test_client, _ = auth_client
        with patch(
            "app.services.portfolio_service.PortfolioService.calculate_stress_test",
            return_value=MOCK_STRESS_RESULT,
        ):
            response = test_client.post(
                "/api/v1/portfolio/stress-test",
                json={
                    "portfolio": SINGLE_ASSET_PORTFOLIO,
                    "scenarios": ["2008_financial_crisis"],
                },
            )
        assert response.status_code == 200
