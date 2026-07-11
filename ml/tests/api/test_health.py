"""
Tests for the ML service health check endpoints.

  GET /health/live
  GET /health/ready
  GET /health
  GET /

All heavy external dependencies (Redis, Weaviate, OpenAI) are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src and root are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ml_client():
    """
    TestClient for the ML FastAPI app.

    Mocks Redis, Weaviate, and OpenAI so no real connections are attempted.
    """
    with (
        patch("src.utils.redis_client.get_async_redis", return_value=AsyncMock()),
        patch("src.services.weaviate.client.WeaviateClientManager.__init__", return_value=None),
        patch("src.api.main.build_readiness_report", new_callable=AsyncMock,
              return_value=(200, {"status": "ok", "components": []})),
        patch("src.api.health.build_liveness_report", return_value={"status": "alive", "version": "1.0.0"}),
        patch("src.api.health.start_openai_canary_monitor", new_callable=AsyncMock),
        patch("src.api.health.stop_openai_canary_monitor", new_callable=AsyncMock),
        patch("src.llm.prompts.PromptLoader.pre_load_all", return_value=None),
        patch("src.api.routes.scraper.load_website_id_map", return_value=None),
    ):
        from src.api.main import create_app
        test_app = create_app()
        with TestClient(test_app, raise_server_exceptions=False) as client:
            yield client


# ── Liveness ──────────────────────────────────────────────────────────────────

class TestLivenessEndpoint:
    """Tests for GET /health/live."""

    def test_returns_200(self, ml_client: TestClient):
        """Liveness check must return HTTP 200."""
        response = ml_client.get("/health/live")
        assert response.status_code == 200

    def test_response_has_status_key(self, ml_client: TestClient):
        """Response must contain a 'status' key."""
        response = ml_client.get("/health/live")
        assert "status" in response.json()

    def test_status_is_alive(self, ml_client: TestClient):
        """Status must be 'alive' for a running service."""
        response = ml_client.get("/health/live")
        body = response.json()
        assert body.get("status") in {"alive", "ok", "healthy"}

    def test_response_has_version(self, ml_client: TestClient):
        """Liveness report must include a version string."""
        response = ml_client.get("/health/live")
        body = response.json()
        assert "version" in body


# ── Readiness ─────────────────────────────────────────────────────────────────

class TestReadinessEndpoint:
    """Tests for GET /health/ready."""

    def test_returns_2xx_when_healthy(self, ml_client: TestClient):
        """When all components are healthy, must return 2xx."""
        response = ml_client.get("/health/ready")
        assert response.status_code < 300

    def test_response_has_status_key(self, ml_client: TestClient):
        """Response must include a 'status' key."""
        response = ml_client.get("/health/ready")
        assert "status" in response.json()

    def test_degraded_returns_503(self):
        """When a required component is down, readiness must return 503."""
        with (
            patch("src.utils.redis_client.get_async_redis", return_value=AsyncMock()),
            patch("src.api.main.build_readiness_report", new_callable=AsyncMock,
                  return_value=(503, {"status": "degraded", "components": []})),
            patch("src.api.health.build_liveness_report", return_value={"status": "alive", "version": "1.0.0"}),
            patch("src.api.health.start_openai_canary_monitor", new_callable=AsyncMock),
            patch("src.api.health.stop_openai_canary_monitor", new_callable=AsyncMock),
            patch("src.llm.prompts.PromptLoader.pre_load_all", return_value=None),
            patch("src.api.routes.scraper.load_website_id_map", return_value=None),
        ):
            from src.api.main import create_app
            degraded_app = create_app()
            with TestClient(degraded_app, raise_server_exceptions=False) as test_client:
                response = test_client.get("/health/ready")
            assert response.status_code == 503



# ── Root ──────────────────────────────────────────────────────────────────────

class TestRootEndpoint:
    """Tests for GET /."""

    def test_returns_200(self, ml_client: TestClient):
        """Root endpoint must return HTTP 200."""
        response = ml_client.get("/")
        assert response.status_code == 200

    def test_response_has_message(self, ml_client: TestClient):
        """Root response must include a 'message' key."""
        response = ml_client.get("/")
        assert "message" in response.json()

    def test_response_has_docs_link(self, ml_client: TestClient):
        """Root response must include a 'docs' link."""
        response = ml_client.get("/")
        assert "docs" in response.json()

    def test_response_has_health_link(self, ml_client: TestClient):
        """Root response must include a 'health' or 'live' link."""
        response = ml_client.get("/")
        body = response.json()
        assert "health" in body or "live" in body
