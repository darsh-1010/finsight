import logging
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from config.settings import settings

logger = logging.getLogger(__name__)

class FallbackAsyncOpenAI:
    """
    A wrapper class that mimics AsyncOpenAI.
    It attempts to use the primary FreeLLMAPI client first.
    If an error occurs, it falls back to the official OpenAI client.
    """

    def __init__(self, api_key: str | None = None) -> None:
        primary_key = settings.freellmapi_key or "dummy-key"
        self._primary_client = AsyncOpenAI(
            api_key=primary_key,
            base_url=settings.freellmapi_base_url
        )
        
        fallback_key = api_key or settings.openai_api_key
        self._fallback_client = AsyncOpenAI(
            api_key=fallback_key
        )
        
        self.chat = self.ChatWrapper(self._primary_client, self._fallback_client)
        self.embeddings = self.EmbeddingsWrapper(self._primary_client, self._fallback_client)
        self.files = self._fallback_client.files
        self.models = self._fallback_client.models
        self.responses = getattr(self._fallback_client, 'responses', None)
        self.beta = self.BetaWrapper(self._primary_client, self._fallback_client)

    class BetaWrapper:
        def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
            self.chat = self.BetaChatWrapper(primary, fallback)
            
        class BetaChatWrapper:
            def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
                self.completions = self.BetaChatCompletionsWrapper(primary, fallback)
                
            class BetaChatCompletionsWrapper:
                def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
                    self.primary = primary
                    self.fallback = fallback
                    
                async def parse(self, *args: Any, **kwargs: Any) -> Any:
                    try:
                        return await self.primary.beta.chat.completions.parse(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"Primary FreeLLMAPI failed for beta.chat.completions.parse: {e}. Falling back to OpenAI.")
                        return await self.fallback.beta.chat.completions.parse(*args, **kwargs)

    class ChatWrapper:
        def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
            self.completions = self.CompletionsWrapper(primary, fallback)

        class CompletionsWrapper:
            def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
                self.primary = primary
                self.fallback = fallback

            async def create(self, *args: Any, **kwargs: Any) -> ChatCompletion | Any:
                try:
                    return await self.primary.chat.completions.create(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Primary FreeLLMAPI failed for chat.completions.create: {e}. Falling back to OpenAI.")
                    return await self.fallback.chat.completions.create(*args, **kwargs)

    class EmbeddingsWrapper:
        def __init__(self, primary: AsyncOpenAI, fallback: AsyncOpenAI):
            self.primary = primary
            self.fallback = fallback

        async def create(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return await self.primary.embeddings.create(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Primary FreeLLMAPI failed for embeddings.create: {e}. Falling back to OpenAI.")
                return await self.fallback.embeddings.create(*args, **kwargs)
