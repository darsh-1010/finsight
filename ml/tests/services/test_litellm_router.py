"""Unit tests for the shared litellm Router (FreeLLMAPI-primary, OpenAI-fallback).

No real API keys are needed - litellm.Router construction only registers
configuration, it doesn't validate credentials or make network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.llm.litellm_router import (
    get_chat_model,
    get_llm_router,
    get_structured_llm_client,
)


class _Output(BaseModel):
    answer: str


def test_router_registers_a_primary_fallback_pair_per_managed_model():
    """Every managed model must have exactly one primary and one fallback
    deployment - two deployments under ONE group name would make litellm
    load-balance randomly between FreeLLMAPI and OpenAI instead of
    deterministically preferring FreeLLMAPI.
    """
    router = get_llm_router()
    group_names = {entry["model_name"] for entry in router.model_list}

    assert "freellmapi/gpt-4o-mini" in group_names
    assert "openai-fallback/gpt-4o-mini" in group_names


def test_router_configures_deterministic_fallback():
    """The Router's `fallbacks` config (not same-group load balancing) is
    what makes FreeLLMAPI always tried first, OpenAI only on failure.
    """
    router = get_llm_router()
    fallback_map = {}
    for entry in router.fallbacks:
        fallback_map.update(entry)

    assert fallback_map.get("freellmapi/gpt-4o-mini") == ["openai-fallback/gpt-4o-mini"]


def test_get_chat_model_targets_the_primary_group():
    chat_model = get_chat_model("gpt-4o-mini", temperature=0.1)
    assert chat_model.model == "freellmapi/gpt-4o-mini"


@pytest.mark.asyncio
async def test_structured_client_populates_parsed():
    """The .beta.chat.completions.parse shim must populate .message.parsed
    from the raw JSON content litellm returns, matching the OpenAI SDK
    ergonomics every existing caller (llm_engine.py, daily_compiler.py,
    weekly_compiler.py, report_compiler.py) already depends on.
    """
    client = get_structured_llm_client()
    router = get_llm_router()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"answer": "42"}'))]

    with patch.object(router, "acompletion", AsyncMock(return_value=mock_response)):
        result = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            response_format=_Output,
        )

    assert result.choices[0].message.parsed == _Output(answer="42")


@pytest.mark.asyncio
async def test_structured_client_requests_the_primary_group_not_the_raw_model():
    """The shim must request the FreeLLMAPI-primary group name, not the raw
    model string passed in by the caller, so the Router's configured
    fallback actually applies.
    """
    client = get_structured_llm_client()
    router = get_llm_router()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"answer": "1"}'))]

    with patch.object(
        router, "acompletion", AsyncMock(return_value=mock_response)
    ) as mock_acompletion:
        await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            response_format=_Output,
        )

    assert mock_acompletion.call_args.kwargs["model"] == "freellmapi/gpt-4o-mini"
