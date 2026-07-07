"""Session Service for managing chat sessions and history.

Handles Redis interactions for session state and conversation history.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis

logger = get_logger(__name__)


class SessionService:
    """Service to handle session state and history management."""

    def __init__(self):
        """Initialize session service."""

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Get full session state from Redis."""
        try:
            key = f"session_state:{session_id}"
            data = await asyncio.to_thread(get_redis().get, key)
            if data:
                return json.loads(data)
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.warning(f"Failed to get session state from Redis: {e}")
        return None

    async def save_session_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Save full session state to Redis with TTL."""
        try:
            key = f"session_state:{session_id}"
            state["last_activity"] = datetime.now(timezone.utc).isoformat()
            state["turn_count"] = state.get("turn_count", 0) + 1
            ttl = getattr(settings, "session_state_ttl", 2592000)
            await asyncio.to_thread(get_redis().setex, key, ttl, json.dumps(state))
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.warning(f"Failed to save session state to Redis: {e}")

    async def set_session_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Write session state without bumping counters."""
        try:
            key = f"session_state:{session_id}"
            ttl = getattr(settings, "session_state_ttl", 2592000)
            await asyncio.to_thread(get_redis().setex, key, ttl, json.dumps(state))
            logger.debug(
                "[SESSION] set_session_state: wrote %d keys for %s",
                len(state),
                session_id,
            )
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.warning("Failed to set session state for %s: %s", session_id, e)

    async def update_session_state(
        self,
        session_id: str,
        *,
        intent: str,
        entities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update session state with new turn information."""
        state = await self.get_session_state(session_id) or {
            "session_id": session_id,
            "created_at": None,
            "entities": {},
            "intent_history": [],
            "constraints": {},
            "conversation_summary": "",
            "turn_count": 0,
        }

        if not state.get("created_at"):
            state["created_at"] = datetime.now(timezone.utc).isoformat()

        if "entities" not in state:
            state["entities"] = {}

        if entities:
            ticker = entities.get("ticker")
            company_name = entities.get("company_name")
            topic = entities.get("topic")
            comparison_tickers = entities.get("comparison_tickers")

            if ticker:
                state["entities"]["primary_ticker"] = ticker
            if company_name:
                state["entities"]["company_name"] = company_name
            if comparison_tickers:
                existing = state["entities"].get("comparison_tickers", [])
                current_set = set(existing)
                for item in comparison_tickers:
                    current_set.add(item)
                state["entities"]["comparison_tickers"] = list(current_set)

            if topic:
                metrics = state["entities"].get("metrics_of_interest", [])
                if topic not in metrics:
                    metrics.append(topic)
                    state["entities"]["metrics_of_interest"] = metrics[-5:]

        if "intent_history" not in state:
            state["intent_history"] = []

        state["intent_history"].append(intent)
        state["intent_history"] = state["intent_history"][-10:]
        state["current_intent"] = intent

        summary_limit = getattr(settings, "session_summary_max_chars", 2000)
        keep_chars = getattr(settings, "session_summary_keep_chars", 1000)

        if len(state.get("conversation_summary", "")) > summary_limit:
            state["conversation_summary"] = state["conversation_summary"][
                -int(keep_chars) :
            ]

        await self.save_session_state(session_id, state)
        return state

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation history from Redis."""
        try:
            key = f"chat_history:{session_id}"
            data = await asyncio.to_thread(get_redis().get, key)
            if data:
                return json.loads(data)
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.warning(f"Failed to get history from Redis: {e}")
        return []

    async def update_history(
        self,
        session_id: str,
        user_message: str,
        ai_response: str,
        ai_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update conversation history in Redis."""
        try:
            key = f"chat_history:{session_id}"
            history_json = await asyncio.to_thread(get_redis().get, key)

            messages = []
            if history_json:
                try:
                    loaded = json.loads(history_json)
                    if isinstance(loaded, list):
                        messages = loaded
                except json.JSONDecodeError:
                    pass

            now_iso = datetime.now(timezone.utc).isoformat()
            messages.append(
                self._build_history_entry(
                    role="user",
                    content=user_message,
                    session_id=session_id,
                    timestamp=now_iso,
                )
            )
            messages.append(
                self._build_history_entry(
                    role="assistant",
                    content=ai_response,
                    session_id=session_id,
                    timestamp=now_iso,
                    metadata=ai_metadata,
                )
            )

            max_history = settings.max_history_turns
            if len(messages) > max_history * 2:
                messages = messages[-(max_history * 2) :]

            ttl = settings.chat_history_ttl
            await asyncio.to_thread(get_redis().setex, key, ttl, json.dumps(messages))
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error("Failed to update history: %s", e)

    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history and session state."""
        try:
            redis_client = get_redis()
            await asyncio.gather(
                asyncio.to_thread(redis_client.delete, f"chat_history:{session_id}"),
                asyncio.to_thread(redis_client.delete, f"session_state:{session_id}"),
            )
            logger.info("Cleared history and state for session %s", session_id)
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            logger.error("Failed to clear session %s: %s", session_id, e)

    def _build_history_entry(
        self,
        role: str,
        content: str,
        session_id: str,
        *,
        timestamp: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a normalized history record that preserves old and new readers."""
        message_type = "human" if role == "user" else "ai"
        entry: dict[str, Any] = {
            "role": role,
            "content": content,
            "session_id": session_id,
            "created_at": timestamp,
            "timestamp": timestamp,
            "type": message_type,
            "data": {"content": content},
        }
        if metadata:
            entry["metadata"] = metadata
        return entry
