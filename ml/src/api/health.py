"""Application health-check helpers."""

from __future__ import annotations

import asyncio
import inspect
import time
from contextlib import suppress
from datetime import UTC, datetime, timezone
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

from config.settings import settings
from src.llm.prompts import PromptLoader
from src.services.weaviate.client import WeaviateClientManager
from src.services.weaviate.embeddings import EmbeddingService
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)

APP_VERSION = "1.0.0"
REQUIRED_PROMPTS = (
    "system/chatbot_system",
    "user/chatbot_message",
    "system/query_expansion",
    "user/query_expansion",
    "system/ticker_resolution",
    "user/ticker_resolution",
)
REQUIRED_CONFIG_FIELDS = (
    "openai_api_key",
    "chatbot_model",
    "query_analysis_model",
    "ticker_resolution_model",
    "redis_url",
    "weaviate_url",
    "weaviate_grpc_url",
)
OPENAI_CANARY_TEXT = "healthcheck"
OPENAI_COMPONENT_NAME = "openai"
OPENAI_CANARY_TASK_NAME = "openai-health-canary"

_openai_canary_task: asyncio.Task | None = None
_openai_canary_lock: asyncio.Lock | None = None
_openai_canary_status: dict[str, Any] = {
    "name": OPENAI_COMPONENT_NAME,
    "status": "failed",
    "details": "canary has not run yet",
    "checked_at": None,
}
_openai_canary_checked_at: float | None = None


def build_liveness_report() -> dict[str, Any]:
    """Return a lightweight liveness payload."""
    return {
        "status": "alive",
        "version": APP_VERSION,
    }


def _build_component_status(
    name: str,
    is_healthy: bool,
    details: str,
) -> dict[str, Any]:
    """Build a normalized component status payload."""
    return {
        "name": name,
        "status": "ok" if is_healthy else "failed",
        "details": details,
    }


def _check_required_config() -> dict[str, Any]:
    """Validate the minimum configuration required for readiness."""
    missing_fields = [
        field_name
        for field_name in REQUIRED_CONFIG_FIELDS
        if not str(getattr(settings, field_name, "")).strip()
    ]

    is_healthy = not missing_fields
    details = (
        "required settings loaded"
        if is_healthy
        else f"missing: {', '.join(missing_fields)}"
    )
    return _build_component_status("config", is_healthy, details)


def _check_prompt_catalog() -> dict[str, Any]:
    """Verify that required prompts are loadable."""
    missing_prompts: list[str] = []

    for prompt_name in REQUIRED_PROMPTS:
        try:
            PromptLoader.load(prompt_name)
        except FileNotFoundError:
            missing_prompts.append(prompt_name)

    is_healthy = not missing_prompts
    details = (
        "required prompts loaded"
        if is_healthy
        else f"missing: {', '.join(missing_prompts)}"
    )
    return _build_component_status("prompts", is_healthy, details)


async def _check_redis_dependency() -> dict[str, Any]:
    """Check Redis readiness without mutating application state."""
    try:
        is_healthy = bool(await get_async_redis().ping())
        details = "ping ok" if is_healthy else "ping returned false"
        return _build_component_status("redis", is_healthy, details)
    except Exception as exc:
        logger.warning(f"[HEALTH] Redis readiness failed: {exc}")
        return _build_component_status("redis", False, str(exc))


def _check_weaviate_dependency() -> dict[str, Any]:
    """Check Weaviate readiness using the existing client manager."""
    try:
        client = WeaviateClientManager.get_client()
        is_healthy = bool(client.is_ready())
        details = "ready" if is_healthy else "not ready"
        return _build_component_status("weaviate", is_healthy, details)
    except Exception as exc:
        logger.warning(f"[HEALTH] Weaviate readiness failed: {exc}")
        return _build_component_status("weaviate", False, str(exc))


def _build_checked_component_status(
    name: str,
    is_healthy: bool,
    details: str,
    checked_at: str | None,
) -> dict[str, Any]:
    """Build a component status with timestamp metadata."""
    status = _build_component_status(name, is_healthy, details)
    status["checked_at"] = checked_at
    return status


def _current_utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for health metadata."""
    return datetime.now(UTC).isoformat()


def _get_openai_canary_lock() -> asyncio.Lock:
    """Create the canary lock lazily so it binds to the active event loop."""
    global _openai_canary_lock
    if _openai_canary_lock is None:
        _openai_canary_lock = asyncio.Lock()
    return _openai_canary_lock


def _set_openai_canary_status(is_healthy: bool, details: str) -> None:
    """Update the cached OpenAI canary result."""
    global _openai_canary_status, _openai_canary_checked_at
    checked_at = _current_utc_timestamp()
    _openai_canary_status = _build_checked_component_status(
        OPENAI_COMPONENT_NAME,
        is_healthy,
        details,
        checked_at,
    )
    _openai_canary_checked_at = time.monotonic()


async def refresh_openai_canary() -> None:
    """Refresh the cached OpenAI dependency status using a small embedding request."""
    if (
        not settings.openai_api_key
        or settings.openai_api_key == "your_openai_api_key_here"
    ):
        _set_openai_canary_status(True, "embedding canary ok (mocked for local dev)")
        return

    canary_lock = _get_openai_canary_lock()
    async with canary_lock:
        try:
            embedding_service = EmbeddingService()
            timeout_seconds = settings.health_openai_canary_timeout_seconds
            await asyncio.wait_for(
                embedding_service.aembed_query(OPENAI_CANARY_TEXT),
                timeout=timeout_seconds,
            )
            details = f"embedding canary ok ({settings.embedding_model})"
            _set_openai_canary_status(True, details)
        except asyncio.TimeoutError:
            _set_openai_canary_status(False, "OpenAI canary timed out")
        except (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            InternalServerError,
            PermissionDeniedError,
            RateLimitError,
            AttributeError,
            ConnectionError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.warning(f"[HEALTH] OpenAI canary failed: {exc}")
            _set_openai_canary_status(False, str(exc))


def _get_openai_dependency_status() -> dict[str, Any]:
    """Return the cached OpenAI dependency status, failing readiness if it is stale."""
    if _openai_canary_checked_at is None:
        return dict(_openai_canary_status)

    age_seconds = time.monotonic() - _openai_canary_checked_at
    stale_after = settings.health_openai_canary_stale_after_seconds
    if age_seconds <= stale_after:
        return dict(_openai_canary_status)

    checked_at = _openai_canary_status.get("checked_at")
    details = f"cached canary stale after {int(age_seconds)}s"
    return _build_checked_component_status(
        OPENAI_COMPONENT_NAME, False, details, checked_at
    )


async def _run_openai_canary_loop() -> None:
    """Refresh the OpenAI canary in the background at a fixed interval."""
    interval_seconds = settings.health_openai_canary_interval_seconds
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            await refresh_openai_canary()
    except asyncio.CancelledError:
        logger.info("[HEALTH] OpenAI canary monitor stopped")
        raise


async def start_openai_canary_monitor() -> None:
    """Prime the cached OpenAI canary and start the background refresh loop."""
    global _openai_canary_task
    await refresh_openai_canary()
    if _openai_canary_task is None or _openai_canary_task.done():
        _openai_canary_task = asyncio.create_task(
            _run_openai_canary_loop(),
            name=OPENAI_CANARY_TASK_NAME,
        )


async def stop_openai_canary_monitor() -> None:
    """Stop the background OpenAI canary task during application shutdown."""
    global _openai_canary_task
    if _openai_canary_task is None:
        return

    _openai_canary_task.cancel()
    with suppress(asyncio.CancelledError):
        await _openai_canary_task
    _openai_canary_task = None


async def build_readiness_report() -> tuple[int, dict[str, Any]]:
    """Build a readiness payload and matching HTTP status code."""
    config_status = _check_required_config()
    prompt_status = _check_prompt_catalog()
    redis_status_result: Any = _check_redis_dependency()
    if inspect.isawaitable(redis_status_result):
        redis_status = await redis_status_result
    else:
        redis_status = redis_status_result
    weaviate_status = _check_weaviate_dependency()
    openai_status = _get_openai_dependency_status()

    components = [
        config_status,
        prompt_status,
        redis_status,
        weaviate_status,
        openai_status,
    ]
    is_ready = all(component["status"] == "ok" for component in components)
    http_status = 200 if is_ready else 503

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "version": APP_VERSION,
        "checks": components,
    }
    return http_status, payload
