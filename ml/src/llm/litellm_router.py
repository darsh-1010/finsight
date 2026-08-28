"""Shared litellm Router: FreeLLMAPI-primary, OpenAI-fallback.

Replaces the hand-rolled try/except fallback pattern duplicated across
FallbackAsyncOpenAI, the LangChain .with_fallbacks() chain, and
FallbackOpenAIEmbeddings with litellm's own tested multi-provider routing,
for the call sites where that's safe (plain chat completions, structured
outputs, embeddings - NOT the OpenAI Responses API or Files API, which
litellm doesn't cover and this codebase still uses directly elsewhere).

Design: each distinct model name gets a (primary, fallback) *pair of
single-deployment groups* rather than two deployments under one group name.
litellm's default routing strategy load-balances randomly across same-named
deployments, which would send traffic to real OpenAI even when FreeLLMAPI is
healthy - the explicit `fallbacks=` mapping is what gives deterministic
"always prefer FreeLLMAPI, only use OpenAI if that call fails" behaviour.
"""

import os
from functools import lru_cache
from typing import Any

import litellm
from langchain_litellm import ChatLiteLLMRouter

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# The fixed, known set of model names requested by in-scope call sites today.
# Adding a new model elsewhere in the app means adding its settings field (or
# env var) here too - litellm can't register a deployment for a name it has
# never seen.
_MANAGED_MODELS = [
    settings.query_analysis_model,
    settings.ticker_resolution_model,
    settings.gpt_4o_mini,
    settings.embedding_model,
    os.getenv("MARKET_INSIGHTS_LLM_MODEL", "gpt-4o-mini"),
]


def _primary_group(model: str) -> str:
    """litellm model-group name for the FreeLLMAPI deployment of `model`."""
    return f"freellmapi/{model}"


def _fallback_group(model: str) -> str:
    """litellm model-group name for the real-OpenAI deployment of `model`."""
    return f"openai-fallback/{model}"


@lru_cache
def get_llm_router() -> litellm.Router:
    """Build the shared FreeLLMAPI-primary/OpenAI-fallback Router.

    One (primary, fallback) single-deployment group pair per distinct model
    name in `_MANAGED_MODELS` (de-duplicated - several settings resolve to
    the same default model string).
    """
    model_list: list[dict[str, Any]] = []
    fallbacks: list[dict[str, list[str]]] = []

    for model in dict.fromkeys(_MANAGED_MODELS):
        primary_name = _primary_group(model)
        fallback_name = _fallback_group(model)

        model_list.append(
            {
                "model_name": primary_name,
                "litellm_params": {
                    "model": f"openai/{model}",
                    "api_base": settings.freellmapi_base_url,
                    "api_key": settings.freellmapi_key or "dummy-key",
                },
            }
        )
        model_list.append(
            {
                "model_name": fallback_name,
                "litellm_params": {
                    "model": f"openai/{model}",
                    "api_key": settings.openai_api_key,
                },
            }
        )
        fallbacks.append({primary_name: [fallback_name]})

    logger.info("[LITELLM_ROUTER] Registered %d managed model(s)", len(model_list) // 2)
    return litellm.Router(model_list=model_list, fallbacks=fallbacks)


def get_embedding_model_group(model_name: str) -> str:
    """The Router model-group name to request for FreeLLMAPI-primary embeddings.

    Used by FallbackOpenAIEmbeddings, which calls `get_llm_router()` directly
    (embeddings has no LangChain-facing or structured-output shim of its own).
    """
    return _primary_group(model_name)


def get_chat_model(model_name: str, temperature: float = 0.0) -> ChatLiteLLMRouter:
    """LangChain-facing chat model: FreeLLMAPI-primary, OpenAI-fallback.

    Drop-in replacement for `ChatOpenAI(model=model_name, temperature=...)`
    at call sites that had no fallback behaviour at all before.
    """
    return ChatLiteLLMRouter(
        router=get_llm_router(),
        model=_primary_group(model_name),
        temperature=temperature,
    )


class LiteLLMStructuredClient:
    """Drop-in replacement for the one `FallbackAsyncOpenAI` method actually
    used across the app: `.beta.chat.completions.parse(...)`.

    Preserves the exact call shape (`model=`, `messages=`,
    `response_format=<PydanticModel>`) and result shape
    (`.choices[0].message.parsed`) so existing callers need zero code changes
    beyond constructing this instead of `FallbackAsyncOpenAI`.
    """

    def __init__(self) -> None:
        self.beta = self._Beta()

    class _Beta:
        def __init__(self) -> None:
            self.chat = self._Chat()

        class _Chat:
            def __init__(self) -> None:
                self.completions = self._Completions()

            class _Completions:
                async def parse(self, *, model: str, messages: list, response_format: type, **kwargs: Any) -> Any:
                    router = get_llm_router()
                    response = await router.acompletion(
                        model=_primary_group(model),
                        messages=messages,
                        response_format=response_format,
                        **kwargs,
                    )
                    content = response.choices[0].message.content
                    response.choices[0].message.parsed = response_format.model_validate_json(content)
                    return response


@lru_cache
def get_structured_llm_client() -> LiteLLMStructuredClient:
    """Get the shared structured-output client (litellm-backed)."""
    return LiteLLMStructuredClient()
