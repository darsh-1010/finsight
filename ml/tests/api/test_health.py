"""Tests for application health helpers."""

import asyncio
import json

from src.api import health as health_module
from src.api.routes import chatbot


def test_build_readiness_report_returns_ready(monkeypatch):
    """Readiness should report healthy when every dependency check passes."""
    monkeypatch.setattr(health_module, "_check_required_config", lambda: {
        "name": "config",
        "status": "ok",
        "details": "required settings loaded",
    })
    monkeypatch.setattr(health_module, "_check_prompt_catalog", lambda: {
        "name": "prompts",
        "status": "ok",
        "details": "required prompts loaded",
    })
    monkeypatch.setattr(health_module, "_check_redis_dependency", lambda: {
        "name": "redis",
        "status": "ok",
        "details": "ping ok",
    })
    monkeypatch.setattr(health_module, "_check_weaviate_dependency", lambda: {
        "name": "weaviate",
        "status": "ok",
        "details": "ready",
    })
    monkeypatch.setattr(health_module, "_get_openai_dependency_status", lambda: {
        "name": "openai",
        "status": "ok",
        "details": "embedding canary ok",
        "checked_at": "2026-04-08T00:00:00+00:00",
    })

    status_code, payload = asyncio.run(health_module.build_readiness_report())

    assert status_code == 200
    assert payload["status"] == "ready"
    assert payload["checks"][-1]["name"] == "openai"


def test_build_readiness_report_returns_not_ready(monkeypatch):
    """Readiness should fail when a dependency check fails."""
    monkeypatch.setattr(health_module, "_check_required_config", lambda: {
        "name": "config",
        "status": "failed",
        "details": "missing: openai_api_key",
    })
    monkeypatch.setattr(health_module, "_check_prompt_catalog", lambda: {
        "name": "prompts",
        "status": "ok",
        "details": "required prompts loaded",
    })
    monkeypatch.setattr(health_module, "_check_redis_dependency", lambda: {
        "name": "redis",
        "status": "ok",
        "details": "ping ok",
    })
    monkeypatch.setattr(health_module, "_check_weaviate_dependency", lambda: {
        "name": "weaviate",
        "status": "failed",
        "details": "not ready",
    })
    monkeypatch.setattr(health_module, "_get_openai_dependency_status", lambda: {
        "name": "openai",
        "status": "failed",
        "details": "OpenAI canary timed out",
        "checked_at": "2026-04-08T00:00:00+00:00",
    })

    status_code, payload = asyncio.run(health_module.build_readiness_report())

    assert status_code == 503
    assert payload["status"] == "not_ready"


def test_build_liveness_report_returns_alive():
    """Liveness should only report that the process is up."""
    payload = health_module.build_liveness_report()

    assert payload["status"] == "alive"
    assert payload["version"] == "1.0.0"


def test_refresh_openai_canary_updates_cached_status(monkeypatch):
    """A successful OpenAI canary should update the cached dependency result."""
    health_module._openai_canary_checked_at = None
    health_module._openai_canary_status = {
        "name": "openai",
        "status": "failed",
        "details": "canary has not run yet",
        "checked_at": None,
    }

    class FakeEmbeddingService:
        """Small fake embedding client for the canary."""

        async def aembed_query(self, _text: str):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(health_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(health_module, "EmbeddingService", FakeEmbeddingService)

    asyncio.run(health_module.refresh_openai_canary())
    component = health_module._get_openai_dependency_status()

    assert component["status"] == "ok"
    assert component["name"] == "openai"
    assert component["checked_at"] is not None


def test_chat_health_endpoint_uses_shared_readiness(monkeypatch):
    """The deprecated chat health route should return the shared readiness payload."""

    async def fake_readiness_report():
        return 503, {
            "status": "not_ready",
            "version": "1.0.0",
            "checks": [{"name": "openai", "status": "failed", "details": "timeout"}],
        }

    monkeypatch.setattr(chatbot, "build_readiness_report", fake_readiness_report)

    response = asyncio.run(chatbot.chat_health())
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "not_ready"
