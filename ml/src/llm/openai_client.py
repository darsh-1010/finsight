"""OpenAI LLM client implementation."""

from typing import Type, TypeVar, cast

from langchain_openai import ChatOpenAI

from config.settings import settings as global_settings
from src.llm.base import BaseLLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)
T = TypeVar("T")


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client using LangChain.

    Provides methods for text generation, structured output, and streaming.
    """

    def __init__(self, settings=None):
        """Initialize OpenAI client with optional settings.

        Args:
            settings: Optional settings object with API key and model config
        """
        self.settings = settings or global_settings
        self._llm = None
        logger.debug(
            f"OpenAIClient initialized with settings: {self.settings is not None}"
        )

    def get_llm(self) -> ChatOpenAI:
        """Get or create ChatOpenAI instance (lazy initialization).

        Returns:
            ChatOpenAI instance
        """
        if self._llm is None:
            logger.debug("LLM instance not found, initializing...")
            self._llm = self._initialize_llm()
        else:
            logger.debug("Returning existing LLM instance")
        return self._llm

    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize ChatOpenAI instance.

        Returns:
            Configured ChatOpenAI instance

        Raises:
            KeyError: If required environment variables are missing
        """
        try:
            # Get from settings
            api_key = self.settings.openai_api_key
            model_name = (
                getattr(self.settings, "openai_model", None)
                or self.settings.gpt_4o_mini
            )

            if not api_key:
                logger.error("OpenAI API key is missing in settings")
                raise ValueError("OPENAI_API_KEY must be configured")

            logger.info(f"Initializing ChatOpenAI with model: {model_name}")

            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                streaming=True,
            )

            logger.info(f"LLM initialized successfully with model: {model_name}")
            return llm

        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error(f"Error initializing LLM: {str(e)}", exc_info=True)
            raise

    async def generate(self, prompt: str | list, **kwargs) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The input prompt (string or list of messages)
            **kwargs: Additional generation parameters

        Returns:
            Generated text response
        """
        llm = self.get_llm()
        response = await llm.ainvoke(prompt, **kwargs)
        return str(response.content)

    async def generate_structured(self, prompt: str, schema: type[T], **kwargs) -> T:
        """Generate a structured response from the LLM.

        Args:
            prompt: The input prompt
            schema: Pydantic model class for response validation
            **kwargs: Additional generation parameters

        Returns:
            Parsed response matching the schema
        """
        llm = self.get_llm()
        structured_llm = llm.with_structured_output(schema)
        result = await structured_llm.ainvoke(prompt, **kwargs)
        return cast(T, result)

    async def stream(self, prompt: str, **kwargs):
        """Stream response chunks from the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters

        Yields:
            Response chunks as they are generated
        """
        llm = self.get_llm()
        async for chunk in llm.astream(prompt, **kwargs):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
