"""Chatbot API endpoints with dependency injection."""

import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from fastapi.responses import JSONResponse, StreamingResponse
from src.llm.fallback_client import FallbackAsyncOpenAI

from config.settings import settings
from src.api.dependencies import get_chat_service
from src.api.health import build_readiness_report
from src.core.interfaces import IChatService
from src.core.schemas import (ChatRequest, ChatResponse,
                              ConversationHistoryResponse, ConversationMessage)
from src.core.tier_feature_resolver import resolver
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis, get_redis

logger = get_logger(__name__)
router = APIRouter()

# Internal API key for trusted callers (e.g. internal microservices).
# Only callers that supply this key are allowed to override tier features.
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _is_trusted_caller(x_internal_api_key: str | None) -> bool:
    """Return True only when the caller supplies the correct internal API key.

    When INTERNAL_API_KEY is not configured (empty string) the check is
    intentionally strict — no caller is considered trusted.  This prevents
    accidental elevation in environments where the key was never set.
    """
    if not _INTERNAL_API_KEY:
        return False
    return x_internal_api_key == _INTERNAL_API_KEY


def _mask_session_id(session_id: str) -> str:
    """Mask session IDs to avoid exposing full identifiers in logs."""
    if len(session_id) <= 8:
        return session_id
    return f"{session_id[:4]}***{session_id[-4:]}"


def _parse_openai_file_id(data_str: str) -> str | None:
    """Helper to parse openai_file_id from legacy or new JSON formats."""
    try:
        meta = json.loads(data_str)
        if not isinstance(meta, dict):
            return data_str
        source = meta.get("source", "openai")
        if source == "openai" and meta.get("file_id"):
            return meta["file_id"]
        return None
    except (json.JSONDecodeError, ValueError):
        return data_str


async def _save_stream_session_task(
    service: IChatService,
    request: ChatRequest,
    stream_context: dict,
) -> None:
    """Persist stream session state after the response has finished sending."""
    await service.save_session_after_stream(
        session_id=request.session_id,
        message=request.user_message,
        response_text=stream_context.get("full_response", ""),
        analysis_result=stream_context.get("analysis_result"),
        citations=stream_context.get("citations", []),
        should_search=stream_context.get("should_search", False),
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: IChatService = Depends(get_chat_service),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> ChatResponse:
    """Process a chat message and return a response."""
    logger.info(f"Chat request: {request.user_message[:50]}...")

    # Only trusted internal callers may override tier features.
    # Frontend / end-user requests always get the canonical tier policy.
    trusted = _is_trusted_caller(x_internal_api_key)
    if request.features and not trusted:
        logger.warning(
            "[TIER_OVERRIDE_REJECTED] Untrusted caller attempted feature override | Tier: %d",
            request.tier,
        )

    # Resolve tier features (with request-level overrides only for trusted callers)
    features = await resolver.resolve(
        tier_id=request.tier,
        override_features=request.features if trusted else None,
        override_tier_name=request.tier_name if trusted else None,
    )

    result = await service.chat(
        message=request.user_message,
        session_id=request.session_id,
        request_id=request.request_id,
        user_id=request.user_id,
        explicit_tickers=request.tickers,
        is_new=request.is_new,
        features=features,  # Pass resolved features
        file_ids=request.file_ids,
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    service: IChatService = Depends(get_chat_service),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> StreamingResponse:
    """Stream a chat response for real-time interaction."""
    logger.info(f"Streaming chat: {request.user_message[:50]}...")

    # Only trusted internal callers may override tier features.
    trusted = _is_trusted_caller(x_internal_api_key)
    if request.features and not trusted:
        logger.warning(
            "[TIER_OVERRIDE_REJECTED_STREAM] Untrusted caller attempted feature override | Tier: %d",
            request.tier,
        )

    # Resolve tier features (with request-level overrides only for trusted callers)
    features = await resolver.resolve(
        tier_id=request.tier,
        override_features=request.features if trusted else None,
        override_tier_name=request.tier_name if trusted else None,
    )

    stream_context: dict = {}

    async def generate() -> AsyncGenerator[str, None]:
        # Emit session event with resolved tier details first
        session_data = {
            "session_id": request.session_id,
            "tier": request.tier,
            "tier_name": features.name,
        }
        yield f"data: {json.dumps({'type': 'session', 'data': session_data})}\n\n"

        async for event in service.stream(
            message=request.user_message,
            session_id=request.session_id,
            request_id=request.request_id,
            user_id=request.user_id,
            explicit_tickers=request.tickers,
            is_new=request.is_new,
            stream_context=stream_context,
            features=features,  # Pass resolved features
            file_ids=request.file_ids,
        ):
            # Skip the 'session' event from service (we just sent a richer one)
            if event.get("type") == "session":
                continue
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    if hasattr(service, "save_session_after_stream"):
        background_tasks.add_task(
            _save_stream_session_task,
            service,
            request,
            stream_context,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/session/{session_id}")
async def clear_history(
    session_id: str,
    _service: IChatService = Depends(get_chat_service),
) -> dict[str, str]:
    """Clear conversation history and context for a session."""
    masked_session_id = _mask_session_id(session_id)
    logger.info("[SESSION_CLEAR_START] session_id=%s", masked_session_id)

    await _service.clear_history(session_id)
    redis_client = get_async_redis()

    try:
        openai_client = FallbackAsyncOpenAI(api_key=settings.openai_api_key)

        # Cleanup OpenAI Files (only files with source=="openai" were uploaded there)
        file_keys = await redis_client.keys(f"openai_file:{session_id}:*")
        for key in file_keys:
            try:
                raw = await redis_client.get(key)
                if not raw:
                    await redis_client.delete(key)
                    continue

                data_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                openai_file_id = _parse_openai_file_id(data_str)

                if openai_file_id:
                    await openai_client.files.delete(openai_file_id)
                    logger.info(
                        "[SESSION_CLEAR] Deleted OpenAI file: %s", openai_file_id
                    )
                await redis_client.delete(key)
            except (ValueError, TypeError, OSError, RuntimeError) as exc:
                logger.warning(
                    "[SESSION_CLEAR] Failed to delete file from OpenAI: %s", exc
                )

        # Clear token tracking and doc limits
        await redis_client.delete(f"session_tokens:{session_id}")
        await redis_client.delete(f"session_docs:{session_id}")

    except (ValueError, TypeError, OSError, RuntimeError) as e:
        logger.warning(
            "[SESSION_CLEAR_OPENAI] Error clearing OpenAI files for %s: %s",
            masked_session_id,
            e,
        )

    try:
        key = f"session_state:{session_id}"
        await redis_client.delete(key)
    except (ValueError, AttributeError, RuntimeError) as exc:
        logger.warning(
            "[SESSION_CLEAR_PARTIAL] session_id=%s | error=%s",
            masked_session_id,
            exc,
        )
    else:
        logger.info("[SESSION_CLEAR_SUCCESS] session_id=%s", masked_session_id)

    return {"status": "success", "message": f"Session {session_id} cleared"}


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    _service: IChatService = Depends(get_chat_service),
) -> dict[str, object | None]:
    """Get session state information."""
    masked_session_id = _mask_session_id(session_id)
    try:
        key = f"session_state:{session_id}"
        data = await asyncio.to_thread(get_redis().get, key)

        if data:
            return {
                "session_id": session_id,
                "exists": True,
                "state": json.loads(data),
            }

        key_legacy = f"session_context:{session_id}"
        data_legacy = await asyncio.to_thread(get_redis().get, key_legacy)
        if data_legacy:
            context = json.loads(data_legacy)
            return {
                "session_id": session_id,
                "exists": True,
                "state": {
                    "entities": {
                        "primary_ticker": context.get("ticker"),
                        "company_name": context.get("company_name"),
                    },
                    "conversation_summary": context.get("last_query"),
                },
            }
    except (ValueError, AttributeError, RuntimeError, json.JSONDecodeError):
        logger.warning(
            "[SESSION_STATE_READ_FAILED] session_id=%s",
            masked_session_id,
            exc_info=True,
        )

    return {
        "session_id": session_id,
        "exists": False,
        "state": None,
    }


@router.get("/session/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    session_id: str,
    service: IChatService = Depends(get_chat_service),
) -> ConversationHistoryResponse:
    """Get conversation history for a session."""
    try:
        raw_messages = await service.get_conversation_history(session_id)
        messages = [ConversationMessage(**message) for message in raw_messages]

        state_key = f"session_state:{session_id}"
        state_data = await asyncio.to_thread(get_redis().get, state_key)
        created_at = None
        turn_count = 0

        if state_data:
            state = json.loads(state_data)
            created_at = state.get("created_at")
            turn_count = state.get("turn_count", 0)

        return ConversationHistoryResponse(
            session_id=session_id,
            messages=messages,
            created_at=created_at,
            turn_count=turn_count,
        )
    except (ValueError, AttributeError, RuntimeError, json.JSONDecodeError) as e:
        logger.error(f"Failed to get conversation history: {e}")
        return ConversationHistoryResponse(
            session_id=session_id,
            messages=[],
            created_at=None,
            turn_count=0,
        )


@router.get("/health", deprecated=True)
async def chat_health() -> JSONResponse:
    """Deprecated chatbot health endpoint that mirrors shared readiness."""
    logger.warning("Deprecated endpoint accessed: /api/v1/chat/health")
    status_code, payload = await build_readiness_report()
    return JSONResponse(status_code=status_code, content=payload)
