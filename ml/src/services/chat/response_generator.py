"""Response Generation Logic."""

import asyncio
import logging
import random
import re
from collections.abc import AsyncGenerator
from typing import Any

# Strip any code fences the LLM produces despite the no-code rule.
# Catches ``` ... ``` blocks (with or without language tag) in all responses.
_CODE_BLOCK_RE = re.compile(r"```[^\n`]*\n?[\s\S]*?```", re.DOTALL)


def _strip_code_blocks(text: str) -> str:
    """Remove markdown code blocks from LLM output before returning to user."""
    stripped = _CODE_BLOCK_RE.sub("", text)
    # Collapse multiple blank lines left behind by removed blocks
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from openai import BadRequestError
from src.llm.fallback_client import FallbackAsyncOpenAI

from config.settings import settings
from src.core.exceptions import LLMError, RateLimitError
from src.llm.prompts import PromptLoader
from src.utils.perf_utils import timed

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Manages LLM interaction, retries, and streaming."""

    def __init__(self, llm: ChatOpenAI) -> None:
        self.llm = llm

    def _extract_content(self, content: Any) -> str:
        """Extract text from LLM content (handles list/multimodal)."""
        if not isinstance(content, list):
            return str(content)

        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
        return "".join(text_parts)

    @staticmethod
    def _is_image_mime(mime_type: str | None) -> bool:
        """Return True when MIME type is an image."""
        return bool(mime_type and mime_type.lower().startswith("image/"))

    def _format_spreadsheet_payload(self, text_content: str, mime_type: str) -> str:
        """Bound spreadsheet text so prompts stay predictable and affordable."""
        max_chars = 12000
        cleaned = text_content.strip()
        is_truncated = len(cleaned) > max_chars
        bounded = cleaned[:max_chars]
        suffix = (
            "\n\n[Spreadsheet truncated due to size limits.]" if is_truncated else ""
        )
        return f"[Attached Spreadsheet Data ({mime_type})]:\n{bounded}{suffix}"

    @staticmethod
    def _extract_response_usage(response: Any) -> dict[str, Any] | None:
        """Normalize usage payload from Responses API objects."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        if isinstance(usage, dict):
            return usage
        if hasattr(usage, "model_dump"):
            return usage.model_dump()
        if hasattr(usage, "dict"):
            return usage.dict()
        return None

    def _extract_response_text(self, response: Any) -> str:
        """Extract generated text from Responses API response object."""
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            return output_text

        text_parts: list[str] = []
        outputs = getattr(response, "output", []) or []
        for item in outputs:
            contents = getattr(item, "content", []) or []
            for content_part in contents:
                part_type = getattr(content_part, "type", "")
                if part_type in {"output_text", "text"}:
                    text_val = getattr(content_part, "text", "")
                    if text_val:
                        text_parts.append(text_val)
        return "".join(text_parts)

    @timed("llm.generate", warn_threshold_s=5.0)
    async def generate(
        self,
        messages: list[BaseMessage],
        model_name: str | None = None,
        max_tokens: int | None = None,
        file_metadata: list[dict] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Generate response with retry logic and optional attached files."""
        if file_metadata:
            return await self.generate_with_files(
                messages, file_metadata, model_name=model_name, max_tokens=max_tokens
            )
        llm = self.llm
        if model_name:
            llm = ChatOpenAI(
                model=model_name,
                temperature=settings.chatbot_temperature,
                max_tokens=max_tokens,
                streaming=True,
            )

        max_attempts = 3
        backoff = 1.0

        for attempt in range(max_attempts):
            try:
                response = await llm.ainvoke(messages)
                response_text = _strip_code_blocks(
                    self._extract_content(response.content)
                )
                usage = (
                    dict(response.usage_metadata) if response.usage_metadata else None
                )
                return response_text, usage
            except (
                ValueError,
                TypeError,
                AttributeError,
                RuntimeError,
                asyncio.TimeoutError,
            ) as exc:
                is_rate_limit = (
                    getattr(exc, "status_code", None) == 429
                    or "rate limit" in str(exc).lower()
                    or "429" in str(exc)
                )

                if attempt == max_attempts - 1:
                    logger.error(
                        "Chat generation failed after %d attempts: %s",
                        max_attempts,
                        exc,
                    )
                    if is_rate_limit:
                        raise RateLimitError(
                            "LLM Provider rate limit exceeded",
                            details={"original_error": str(exc)},
                        ) from exc
                    raise LLMError(
                        f"LLM Provider failed: {exc}",
                        details={"original_error": str(exc)},
                    ) from exc

                if not is_rate_limit:
                    logger.warning(
                        "Generation attempt %d failed with non-rate-limit error: %s. Retrying...",
                        attempt + 1,
                        exc,
                    )

                sleep_for = random.uniform(0.5, backoff)
                logger.warning(
                    "LLM attempt %d failed, retrying in %.2fs", attempt + 1, sleep_for
                )
                await asyncio.sleep(sleep_for)
                backoff = min(backoff * 2, 8.0)

        return "", None

    @timed("llm.stream_setup", warn_threshold_s=2.0)
    async def stream(
        self,
        messages: list[BaseMessage],
        model_name: str | None = None,
        max_tokens: int | None = None,
        file_metadata: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream response content and tool statuses."""
        if file_metadata:
            full_response = ""
            usage_payload: dict[str, Any] | None = None
            async for event in self.stream_with_files(
                messages,
                file_metadata,
                model_name=model_name,
                max_tokens=max_tokens,
            ):
                if event["type"] == "content":
                    full_response += event["data"]
                if event["type"] == "usage":
                    usage_payload = event["data"]
                yield event

            if usage_payload:
                yield {"type": "usage", "data": usage_payload}
            yield {"type": "complete_text", "data": full_response}
            return

        llm = self.llm
        if model_name:
            llm = ChatOpenAI(
                model=model_name,
                temperature=settings.chatbot_temperature,
                max_tokens=max_tokens,
                streaming=True,
                stream_options={"include_usage": True},
            )

        search_indicator_shown = False
        full_response = ""
        tokens_used = None

        try:
            async for chunk in llm.astream(messages):
                if (
                    hasattr(chunk, "tool_calls")
                    and chunk.tool_calls
                    and not search_indicator_shown
                ):
                    status_msg = PromptLoader.load("notices/web_search_status")
                    yield {"type": "status", "data": status_msg}
                    search_indicator_shown = True

                if hasattr(chunk, "content") and chunk.content:
                    content_to_add = self._extract_content(chunk.content)
                    if content_to_add:
                        full_response += content_to_add
                        yield {"type": "content", "data": content_to_add}

                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    tokens_used = chunk.usage_metadata

            if tokens_used:
                yield {"type": "usage", "data": tokens_used}
            yield {"type": "complete_text", "data": full_response}

        except (
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.error("Stream failed: %s", exc, exc_info=True)
            yield {"type": "error", "data": str(exc)}

    async def stream_with_files(
        self,
        messages: list[BaseMessage],
        file_metadata: list[dict],
        *,
        model_name: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream responses for attachment-bearing prompts using Responses API."""
        client = FallbackAsyncOpenAI(api_key=settings.openai_api_key)
        responses_input = self._build_responses_input(messages, file_metadata)

        try:
            stream = await client.responses.create(
                model=model_name or settings.chatbot_model,
                input=responses_input,
                max_output_tokens=max_tokens,
                temperature=settings.chatbot_temperature,
                stream=True,
            )
            async for event in stream:
                res = self._parse_stream_event(event)
                if res:
                    yield res

        except BadRequestError as exc:
            logger.error("[FILE_STREAM_BAD_REQUEST] %s", exc)
            yield {"type": "error", "data": str(exc)}
        except (
            ValueError,
            TypeError,
            OSError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.error("[FILE_STREAM_ERROR] %s", exc, exc_info=True)
            yield {"type": "error", "data": str(exc)}

    def _parse_stream_event(self, event: Any) -> dict[str, Any] | None:
        """Parse stream event and return response payload."""
        event_type = getattr(event, "type", "")
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            if delta:
                return {"type": "content", "data": delta}
        elif event_type == "response.completed":
            response_obj = getattr(event, "response", None)
            usage = self._extract_response_usage(response_obj)
            if usage:
                return {"type": "usage", "data": usage}
        elif event_type == "error":
            error_obj = getattr(event, "error", None)
            error_message = getattr(error_obj, "message", "Unknown error")
            return {"type": "error", "data": error_message}
        return None

    @timed("llm.generate_with_files", warn_threshold_s=5.0)
    async def generate_with_files(
        self,
        messages: list[BaseMessage],
        file_metadata: list[dict],
        *,
        model_name: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Generate a response using Responses API with mixed attachments."""
        client = FallbackAsyncOpenAI(api_key=settings.openai_api_key)
        responses_input = self._build_responses_input(messages, file_metadata)

        try:
            response = await client.responses.create(
                model=model_name or settings.chatbot_model,
                input=responses_input,
                max_output_tokens=max_tokens,
                temperature=settings.chatbot_temperature,
            )
            return _strip_code_blocks(
                self._extract_response_text(response)
            ), self._extract_response_usage(response)
        except BadRequestError as exc:
            logger.error("[FILE_GENERATION_BAD_REQUEST] %s", exc)
            return "", None
        except (
            ValueError,
            TypeError,
            OSError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.error("Failed to generate with files using responses api: %s", exc)
            return "", None

    def _build_responses_input(
        self,
        messages: list[BaseMessage],
        file_metadata: list[dict],
    ) -> list[dict[str, Any]]:
        """Build Responses API input with message-level multimodal content."""
        api_input: list[dict[str, Any]] = []
        for msg in messages:
            role = (
                "user"
                if msg.type == "human"
                else "assistant" if msg.type == "ai" else "system"
            )

            # OpenAI Responses API requires 'output_text' for assistant role and 'input_text' for others
            content_type = "output_text" if role == "assistant" else "input_text"

            content: list[dict[str, Any]] = [
                {"type": content_type, "text": self._extract_content(msg.content)}
            ]
            if msg == messages[-1] and role == "user":
                content.extend(self._build_attachment_items(file_metadata))
            api_input.append({"role": role, "content": content})
        return api_input

    def _build_attachment_items(
        self, file_metadata: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert stored attachment metadata into Responses API input items."""
        attachments: list[dict[str, Any]] = []
        for meta in file_metadata:
            source = meta.get("source", "openai")
            mime_type = str(meta.get("mime_type") or "application/pdf")
            file_id = meta.get("file_id")

            # Case 1: Inline Base64 Images (e.g. uploaded via UI directly)
            if source == "base64" and meta.get("base64_data"):
                attachments.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{meta['base64_data']}",
                        "detail": "auto",
                    }
                )
                logger.info(
                    "[VISION] Attached inline base64 image (type: %s)", mime_type
                )
                continue

            # Case 2: OpenAI Hosted Images (Vision-compatible)
            if file_id and self._is_image_mime(mime_type):
                attachments.append(
                    {"type": "input_image", "file_id": file_id, "detail": "auto"}
                )
                logger.info(
                    "[VISION] Attached image file ID: %s (type: %s)", file_id, mime_type
                )
                continue

            # Case 3: All other OpenAI Hosted Files (PDF, Word, Excel, CSV)
            if file_id:
                attachments.append({"type": "input_file", "file_id": file_id})
                logger.info(
                    "[FILE] Attached OpenAI document: %s (type: %s)", file_id, mime_type
                )
                continue

            # Case 4: Inline Text Content (spreadsheet extracted to plain text)
            text_content = meta.get("text_content")
            if source == "text" and text_content:
                formatted = self._format_spreadsheet_payload(text_content, mime_type)
                attachments.append({"type": "input_text", "text": formatted})
                logger.info(
                    "[TEXT] Attached inline spreadsheet text (type: %s)", mime_type
                )
                continue

            logger.warning("[FILE_SKIP] No usable content for metadata: %s", meta)

        return attachments
