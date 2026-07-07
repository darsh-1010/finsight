"""Base LLM client abstract class."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Type, TypeVar

T = TypeVar("T")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients.

    Provides a consistent interface for different LLM providers.
    """

    @abstractmethod
    def get_llm(self) -> Any:
        """Get the underlying LLM instance.

        Returns:
            The LLM instance (e.g., ChatOpenAI)
        """

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated text response
        """

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[T], **kwargs) -> T:
        """Generate a structured response from the LLM.

        Args:
            prompt: The input prompt
            schema: Pydantic model class for response validation
            **kwargs: Additional generation parameters

        Returns:
            Parsed response matching the schema
        """

    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream response chunks from the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters

        Yields:
            Response chunks as they are generated
        """
        yield ""
