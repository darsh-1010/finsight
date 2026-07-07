"""Backend-backed chat history hydration for Redis sessions."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import redis.asyncio as redis_async
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field, ValidationError
from redis.exceptions import RedisError

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)


class BackendChatHistoryMessage(BaseModel):
    """Single history row returned by the backend chat-history API."""

    content: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    non_substantive: bool = Field(default=False)
    id: int | None = Field(default=None)
    session_id: str | int | None = Field(default=None)
    created_at: str | None = Field(default=None)


class ChatHistoryService:
    """Fetch, normalize, and cache chat history for session continuity."""

    def __init__(
        self,
        redis_client: redis_async.Redis[str] | None = None,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._redis = redis_client or get_async_redis()
        self._http_client_factory = (
            http_client_factory or self._default_http_client_factory
        )

    async def get_raw_history(
        self, session_id: str, is_new: bool
    ) -> list[dict[str, Any]]:
        """Get standardized history records for a session."""
        masked_session_id = self._mask_session_id(session_id)
        if is_new:
            logger.info(
                f"[CHAT_HISTORY_BYPASS] session_id={masked_session_id} | reason=is_new"
            )
            logger.info(
                f"[Chat History] Starting a new chat, so previous messages are skipped | session_id={masked_session_id}"
            )
            return []

        cached_history = await self._read_cached_history(session_id)
        if cached_history:
            logger.info(
                f"[CHAT_HISTORY_SOURCE] session_id={masked_session_id} | "
                f"source=redis | messages={len(cached_history)}"
            )
            logger.info(
                f"[Chat History] Found existing chat messages in Redis cache | "
                f"session_id={masked_session_id} | messages={len(cached_history)}"
            )
            return cached_history

        logger.info(
            f"[CHAT_HISTORY_REDIS_MISS] session_id={masked_session_id} | fallback=backend"
        )
        logger.info(
            f"[Chat History] No cached chat found in Redis, trying backend history API | "
            f"session_id={masked_session_id}"
        )
        fetched_history = await self._fetch_remote_history(session_id)
        if fetched_history:
            await self._cache_history(session_id, fetched_history)
            logger.info(
                f"[CHAT_HISTORY_SOURCE] session_id={masked_session_id} | "
                f"source=backend | messages={len(fetched_history)}"
            )
            logger.info(
                f"[Chat History] Loaded chat history from backend API | "
                f"session_id={masked_session_id} | messages={len(fetched_history)}"
            )
        else:
            logger.warning(
                f"[CHAT_HISTORY_EMPTY] session_id={masked_session_id} | source=backend"
            )
            logger.warning(
                f"[Chat History] Backend API returned no usable chat history | "
                f"session_id={masked_session_id}"
            )
        return fetched_history

    async def get_history_messages(
        self, session_id: str, is_new: bool
    ) -> list[BaseMessage]:
        """Get cached or backend chat history as LangChain messages."""
        masked_session_id = self._mask_session_id(session_id)
        raw_history = await self.get_raw_history(session_id, is_new)
        messages: list[BaseMessage] = []
        for record in raw_history:
            role = record.get("role")
            content = record.get("content")
            if not isinstance(content, str) or not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        logger.info(
            f"[CHAT_HISTORY_MESSAGES_READY] session_id={masked_session_id} | "
            f"messages={len(messages)}"
        )
        logger.info(
            f"[Chat History] Chat context messages are ready for prompt building | "
            f"session_id={masked_session_id} | messages={len(messages)}"
        )
        return messages

    async def clear_cache(self, session_id: str) -> None:
        """Delete the Redis cache entry for a session history."""
        await self._redis.delete(self._cache_key(session_id))

    async def _read_cached_history(self, session_id: str) -> list[dict[str, Any]]:
        """Read a cached history payload from Redis and normalize it."""
        cache_key = self._cache_key(session_id)
        masked_session_id = self._mask_session_id(session_id)
        logger.info(
            f"[CHAT_HISTORY_REDIS_LOOKUP] session_id={masked_session_id} | "
            f"key=chat_history:<masked>"
        )
        logger.info(
            f"[Chat History] Checking Redis cache for previous chat messages | "
            f"session_id={masked_session_id}"
        )
        try:
            raw_payload = await self._redis.get(cache_key)
        except (RedisError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.warning(
                f"[CHAT_HISTORY_REDIS_LOOKUP_FAILED] session_id={masked_session_id} | "
                f"error={exc}"
            )
            logger.warning(
                f"[Chat History] Redis lookup failed while reading cached chat messages | "
                f"session_id={masked_session_id} | error={exc}"
            )
            return []

        if not raw_payload:
            logger.info(
                f"[CHAT_HISTORY_REDIS_MISS_DETAIL] session_id={masked_session_id} | "
                f"key=chat_history:<masked>"
            )
            logger.info(
                f"[Chat History] Redis cache does not have chat history for this session | "
                f"session_id={masked_session_id}"
            )
            return []

        try:
            loaded_payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning(
                f"[CHAT_HISTORY_CACHE_INVALID] session_id={masked_session_id} | reason=invalid_json"
            )
            return []

        if not isinstance(loaded_payload, list):
            logger.warning(
                f"[CHAT_HISTORY_CACHE_INVALID] session_id={masked_session_id} | reason=non_list_payload"
            )
            return []

        normalized_history: list[dict[str, Any]] = []
        for item in loaded_payload:
            if isinstance(item, dict):
                normalized_item = self._normalize_record(item, session_id)
                if normalized_item:
                    normalized_history.append(normalized_item)
        logger.info(
            f"[CHAT_HISTORY_REDIS_HIT] session_id={masked_session_id} | "
            f"key=chat_history:<masked> | records={len(normalized_history)}"
        )
        logger.info(
            f"[Chat History] Redis cache returned chat history successfully | "
            f"session_id={masked_session_id} | records={len(normalized_history)}"
        )
        return normalized_history

    async def _fetch_remote_history(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch history rows from the backend service."""
        masked_session_id = self._mask_session_id(session_id)
        token = settings.ml_data_transfer_token
        if not token:
            logger.warning(
                f"[CHAT_HISTORY_TOKEN_MISSING] session_id={masked_session_id}"
            )
            logger.warning(
                f"[Chat History] Backend token is missing, cannot call chat history API | "
                f"session_id={masked_session_id}"
            )
            return []

        request_url = self._build_request_url(session_id)
        request_limit = self._resolve_message_limit()
        headers = {"accept": "application/json", "x-ml-token": token}
        logger.info(
            f"[CHAT_HISTORY_BACKEND_FETCH_START] session_id={masked_session_id} | "
            f"limit={request_limit} | endpoint=ml-data-transfer/chat-history"
        )
        logger.info(
            f"[Chat History] Calling backend API to fetch previous chat messages | "
            f"session_id={masked_session_id} | limit={request_limit}"
        )

        try:
            async with self._http_client_factory() as client:
                response = await client.get(
                    request_url,
                    params={"limit": request_limit},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning(
                f"[CHAT_HISTORY_BACKEND_FETCH_FAILED] session_id={masked_session_id} | "
                f"error={exc}"
            )
            logger.warning(
                f"[Chat History] Backend API call failed while fetching chat history | "
                f"session_id={masked_session_id} | error={exc}"
            )
            return []

        normalized_history = self._normalize_remote_payload(payload, session_id)
        logger.info(
            f"[CHAT_HISTORY_BACKEND_FETCH_SUCCESS] session_id={masked_session_id} | "
            f"status={response.status_code} | records={len(normalized_history)}"
        )
        logger.info(
            f"[Chat History] Backend API returned chat history successfully | "
            f"session_id={masked_session_id} | records={len(normalized_history)}"
        )
        return normalized_history

    async def _cache_history(
        self, session_id: str, history: list[dict[str, Any]]
    ) -> None:
        """Persist normalized history rows to Redis with the session TTL."""
        cache_key = self._cache_key(session_id)
        masked_session_id = self._mask_session_id(session_id)
        logger.info(
            f"[CHAT_HISTORY_CACHE_WRITE_START] session_id={masked_session_id} | "
            f"key=chat_history:<masked> | records={len(history)} | "
            f"ttl={settings.chat_history_ttl}"
        )
        logger.info(
            f"[Chat History] Saving backend chat history to Redis cache | "
            f"session_id={masked_session_id} | records={len(history)}"
        )
        try:
            await self._redis.setex(
                cache_key,
                settings.chat_history_ttl,
                json.dumps(history),
            )
        except (RedisError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            logger.warning(
                f"[CHAT_HISTORY_CACHE_WRITE_FAILED] session_id={masked_session_id} | "
                f"error={exc}"
            )
            logger.warning(
                f"[Chat History] Failed to save chat history in Redis cache | "
                f"session_id={masked_session_id} | error={exc}"
            )
            raise
        logger.info(
            f"[CHAT_HISTORY_CACHE_WRITE_SUCCESS] session_id={masked_session_id} | "
            f"key=chat_history:<masked>"
        )
        logger.info(
            f"[Chat History] Chat history saved in Redis cache successfully | "
            f"session_id={masked_session_id}"
        )

    def _normalize_remote_payload(
        self,
        payload: Any,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Convert backend payloads into the Redis-compatible history shape."""
        masked_session_id = self._mask_session_id(session_id)
        raw_records = self._extract_records(payload)
        normalized_history: list[dict[str, Any]] = []

        for raw_record in raw_records:
            try:
                validated_record = BackendChatHistoryMessage.model_validate(raw_record)
            except ValidationError:
                continue

            normalized_history.append(
                self._build_normalized_record(validated_record, session_id)
            )

        dropped_records = len(raw_records) - len(normalized_history)
        logger.info(
            f"[CHAT_HISTORY_NORMALIZE_SUMMARY] session_id={masked_session_id} | "
            f"raw_records={len(raw_records)} | normalized_records={len(normalized_history)}"
        )
        logger.info(
            f"[Chat History] Converted backend payload into Redis chat format | "
            f"session_id={masked_session_id} | raw_records={len(raw_records)} | "
            f"normalized_records={len(normalized_history)}"
        )
        if dropped_records > 0:
            logger.warning(
                f"[CHAT_HISTORY_NORMALIZE_DROPPED] session_id={masked_session_id} | "
                f"dropped_records={dropped_records}"
            )
            logger.warning(
                f"[Chat History] Some backend messages were skipped due to invalid format | "
                f"session_id={masked_session_id} | dropped_records={dropped_records}"
            )
        return normalized_history

    def _normalize_record(
        self,
        record: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any] | None:
        """Normalize an existing Redis record into the canonical cache shape."""
        role = self._normalize_role(record.get("role") or record.get("type"))
        content = self._extract_content(record)
        if not role or not content:
            return None

        timestamp = record.get("timestamp") or record.get("created_at")
        metadata = (
            record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        )

        return {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "created_at": timestamp,
            "session_id": str(record.get("session_id") or session_id),
            "type": "human" if role == "user" else "ai",
            "data": {"content": content},
            "metadata": metadata,
        }

    def _build_normalized_record(
        self,
        record: BackendChatHistoryMessage,
        session_id: str,
    ) -> dict[str, Any]:
        """Convert a validated backend record into the Redis cache format."""
        role = self._normalize_role(record.role) or "assistant"
        timestamp = record.created_at
        metadata = {
            "source": "backend_chat_history",
            "message_id": record.id,
            "non_substantive": record.non_substantive,
        }

        return {
            "role": role,
            "content": record.content,
            "timestamp": timestamp,
            "created_at": timestamp,
            "session_id": str(record.session_id or session_id),
            "id": record.id,
            "type": "human" if role == "user" else "ai",
            "data": {"content": record.content},
            "metadata": metadata,
        }

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        """Extract a list of message records from a backend response payload."""
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if not isinstance(payload, dict):
            return []

        for key in ("data", "messages", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        return [payload]

    def _extract_content(self, record: dict[str, Any]) -> str:
        """Extract content from either the new or legacy history shape."""
        content = record.get("content")
        if isinstance(content, str):
            return content.strip()

        data = record.get("data")
        if isinstance(data, dict):
            nested_content = data.get("content")
            if isinstance(nested_content, str):
                return nested_content.strip()

        return ""

    def _normalize_role(self, role: Any) -> str | None:
        """Map backend roles to the canonical chat roles used by Redis."""
        if not isinstance(role, str):
            return None

        normalized_role = role.strip().lower()
        if normalized_role in {"user", "human"}:
            return "user"
        if normalized_role in {"assistant", "ai", "bot"}:
            return "assistant"
        return None

    def _build_request_url(self, session_id: str) -> str:
        """Build the backend chat-history endpoint URL."""
        base_url = str(settings.ml_data_transfer_base_url).rstrip("/")
        return f"{base_url}/api/v1/ml-data-transfer/chat-history/{session_id}"

    def _resolve_message_limit(self) -> int:
        """Clamp backend history retrieval to the supported maximum."""
        return max(1, min(settings.max_message_retrieved, 10))

    def _cache_key(self, session_id: str) -> str:
        """Build the Redis cache key for a chat history."""
        return f"chat_history:{session_id}"

    def _default_http_client_factory(self) -> httpx.AsyncClient:
        """Create an HTTP client with a bounded timeout for backend fetches."""
        return httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout))

    def _mask_session_id(self, session_id: str) -> str:
        """Mask session IDs to keep logs useful without exposing full identifiers."""
        if len(session_id) <= 8:
            return session_id
        return f"{session_id[:4]}***{session_id[-4:]}"
