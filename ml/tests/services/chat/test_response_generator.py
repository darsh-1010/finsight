"""Tests for attachment-aware response generation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.services.chat.response_generator import ResponseGenerator


@pytest.fixture
def generator() -> ResponseGenerator:
    """Create generator with a mocked base llm."""
    return ResponseGenerator(llm=MagicMock())


def _build_messages() -> list:
    return [
        SystemMessage(content="You are helpful."),
        HumanMessage(content="Analyze the attached files."),
    ]


def test_build_attachment_items_routes_pdf_image_and_sheet(generator: ResponseGenerator) -> None:
    """Attachment router should map each source to correct Responses API item type."""
    metadata = [
        {"source": "openai", "file_id": "file-pdf", "mime_type": "application/pdf"},
        {"source": "base64", "base64_data": "abc123", "mime_type": "image/png"},
        {"source": "text", "text_content": "col1,col2\n1,2", "mime_type": "application/vnd.ms-excel"},
    ]

    items = generator._build_attachment_items(metadata)

    assert items[0] == {"type": "input_file", "file_id": "file-pdf"}
    assert items[1]["type"] == "input_image"
    assert items[1]["image_url"].startswith("data:image/png;base64,")
    assert items[2]["type"] == "input_text"


def test_build_responses_input_attaches_only_last_user_message(generator: ResponseGenerator) -> None:
    """Attachments should be attached only to final user message."""
    metadata = [{"source": "openai", "file_id": "file-pdf", "mime_type": "application/pdf"}]

    payload = generator._build_responses_input(_build_messages(), metadata)

    assert payload[0]["role"] == "system"
    assert len(payload[0]["content"]) == 1
    assert payload[1]["role"] == "user"
    assert len(payload[1]["content"]) == 2
    assert payload[1]["content"][1] == {"type": "input_file", "file_id": "file-pdf"}


@pytest.mark.anyio
async def test_generate_with_files_uses_responses_api(monkeypatch: pytest.MonkeyPatch, generator: ResponseGenerator) -> None:
    """Attachment generation should call responses API and parse text/usage."""

    class FakeResponses:
        async def create(self, **kwargs):
            assert kwargs["input"][1]["content"][1]["type"] == "input_file"
            return SimpleNamespace(
                output_text="final answer",
                usage={"total_tokens": 42, "input_tokens": 20, "output_tokens": 22},
            )

    class FakeClient:
        def __init__(self, api_key: str):
            self.responses = FakeResponses()

    monkeypatch.setattr("src.services.chat.response_generator.FallbackAsyncOpenAI", FakeClient)

    text, usage = await generator.generate_with_files(
        _build_messages(),
        [{"source": "openai", "file_id": "file-pdf", "mime_type": "application/pdf"}],
    )

    assert text == "final answer"
    assert usage and usage["total_tokens"] == 42


@pytest.mark.anyio
async def test_stream_with_files_emits_delta_and_usage(monkeypatch: pytest.MonkeyPatch, generator: ResponseGenerator) -> None:
    """Attachment streaming should map Responses events to service events."""

    async def fake_event_stream():
        yield SimpleNamespace(type="response.output_text.delta", delta="Hello")
        yield SimpleNamespace(type="response.output_text.delta", delta=" world")
        yield SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(usage={"total_tokens": 11}),
        )

    class FakeResponses:
        async def create(self, **kwargs):
            assert kwargs["stream"] is True
            return fake_event_stream()

    class FakeClient:
        def __init__(self, api_key: str):
            self.responses = FakeResponses()

    monkeypatch.setattr("src.services.chat.response_generator.FallbackAsyncOpenAI", FakeClient)

    events = []
    async for event in generator.stream_with_files(
        _build_messages(),
        [{"source": "openai", "file_id": "file-pdf", "mime_type": "application/pdf"}],
    ):
        events.append(event)

    assert events[0] == {"type": "content", "data": "Hello"}
    assert events[1] == {"type": "content", "data": " world"}
    assert events[2] == {"type": "usage", "data": {"total_tokens": 11}}
