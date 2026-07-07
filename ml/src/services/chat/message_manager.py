"""Message and Session Logic Manager."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.services.session_service import SessionService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MessageManager:
    """Manages chat history, session state logic, and query enrichment."""

    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    async def get_history_messages(self, session_id: str) -> list[BaseMessage]:
        """Get conversation history as LangChain messages."""
        history_json = await self.session_service.get_history(session_id)
        messages: list[BaseMessage] = []
        for msg in history_json:
            if isinstance(msg, dict):
                role = msg.get("role") or msg.get("type")
                data: Any = msg.get("data", {})
                content = (
                    data.get("content")
                    if isinstance(data, dict)
                    else msg.get("content")
                )
                if not isinstance(content, str) or not content:
                    continue

                if role in ["user", "human"]:
                    messages.append(HumanMessage(content=content))
                elif role in ["assistant", "ai", "bot"]:
                    messages.append(AIMessage(content=content))
        return messages

    async def get_session_state(self, session_id: str) -> dict[str, Any]:
        """Get raw session state."""
        return await self.session_service.get_session_state(session_id) or {}

    async def get_raw_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get raw conversation history in standardized format."""
        history = await self.session_service.get_history(session_id)
        standardized: list[dict[str, Any]] = []
        for msg in history:
            if isinstance(msg, dict):
                role_type = msg.get("role") or msg.get("type")
                role = "user" if role_type in ["user", "human"] else "assistant"
                data: Any = msg.get("data", {})
                content = (
                    data.get("content")
                    if isinstance(data, dict)
                    else msg.get("content")
                )
                if not isinstance(content, str) or not content:
                    continue

                standardized.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": msg.get("timestamp") or msg.get("created_at"),
                        "created_at": msg.get("created_at") or msg.get("timestamp"),
                        "session_id": msg.get("session_id"),
                        "metadata": msg.get("metadata"),
                    }
                )
        return standardized

    async def clear_session(self, session_id: str) -> None:
        """Clear session data."""
        await self.session_service.clear_history(session_id)

    def enrich_query(self, message: str, state: dict[str, Any] | None) -> str:
        """Enrich user message with session context hints."""
        if not state:
            return message

        entities = state.get("entities", {})
        hints = []

        if ticker := entities.get("primary_ticker"):
            hints.append(f"topic: {entities.get('company_name', ticker)}")
        if comparisons := entities.get("comparison_tickers"):
            hints.append(f"comparing: {', '.join(comparisons)}")
        if history := state.get("intent_history"):
            hints.append(f"last intent: {history[-1]}")

        if hints:
            context_hint = "; ".join(hints)
            logger.debug(f"Enriched query: {context_hint}")
            return f"{message} (context: {context_hint})"

        return message

    def build_context_summary(self, state: dict[str, Any] | None) -> str:
        """Build a summary string of the session context."""
        if not state:
            return ""

        parts = ["[Session Context]"]
        entities = state.get("entities", {})

        if entities.get("company_name") or entities.get("primary_ticker"):
            company = entities.get("company_name", "")
            ticker = entities.get("primary_ticker", "")
            parts.append(
                f"- Previous Topic: {company} ({ticker})"
                if company
                else f"- Previous Topic: {ticker}"
            )

        if entities.get("comparison_tickers"):
            parts.append(
                f"- Comparison Entities: {', '.join(entities['comparison_tickers'])}"
            )

        if intent_history := state.get("intent_history", []):
            parts.append(f"- Intent History: {' → '.join(intent_history[-3:])}")

        if entities.get("metrics_of_interest"):
            parts.append(
                f"- User Focus: {', '.join(entities['metrics_of_interest'][-3:])}"
            )

        return "\n".join(parts) if len(parts) > 1 else ""

    async def update_session_after_turn(
        self,
        session_id: str,
        message: str,
        result: dict[str, Any],
        _citations: list[dict[str, Any]],
    ) -> None:
        """Update session state based on the latest turn's analysis."""
        if not session_id or not result.get("contexts"):
            return

        contexts = result["contexts"]
        first_ctx = contexts[0]

        expansion = result.get("expansion", {})
        intent = expansion.get("intent", "query")

        topic = self._extract_topic(intent or message)

        await self.session_service.update_session_state(
            session_id=session_id,
            intent=intent,
            entities={
                "ticker": first_ctx.get("ticker"),
                "company_name": first_ctx.get("company_name"),
                "topic": topic,
                "comparison_tickers": (
                    [c["ticker"] for c in contexts[1:]] if len(contexts) > 1 else None
                ),
            },
        )

        updated_state = await self.session_service.get_session_state(session_id)
        summary = self.build_context_summary(updated_state)
        if summary and updated_state:
            updated_state["conversation_summary"] = summary
            await self.session_service.set_session_state(session_id, updated_state)

    async def update_history(
        self,
        session_id: str,
        user_message: str,
        ai_response: str,
        ai_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update conversation history."""
        await self.session_service.update_history(
            session_id, user_message, ai_response, ai_metadata
        )

    def _extract_topic(self, text: str) -> str:
        """Extract a brief topic from intent or query text."""
        if not text:
            return ""
        topic = text.replace("understand_", "").replace("_", " ")
        topic = topic.replace("retrieve ", "").replace("get ", "")
        return topic[:60] if len(topic) > 60 else topic
