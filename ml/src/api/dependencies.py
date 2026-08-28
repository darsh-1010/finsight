"""FastAPI dependency injection.

Provides service instances to API routes using FastAPI's Depends.
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from config.settings import settings
from src.core.container import Container
from src.core.interfaces import IChatService, IQueryService, IRAGService, ITickerService
from src.llm.fallback_client import FallbackAsyncOpenAI
from src.llm.litellm_router import get_structured_llm_client
from src.services.chat.context_manager import ContextManager
from src.services.chat.history_service import ChatHistoryService
from src.services.chat.message_manager import MessageManager
from src.services.chat.response_generator import ResponseGenerator
from src.services.chat_service import ChatService
from src.services.query_service import QueryService
from src.services.rag import RAGService
from src.services.research.report_compiler import ResearchReportCompiler
from src.services.session_service import SessionService
from src.services.ticker_service import TickerService
from src.services.uploads.user_upload_service import UserUploadService
from src.utils.redis_client import get_async_redis


def _bootstrap_container() -> None:
    """Register all services with the container."""
    if not Container.is_registered(IQueryService):
        Container.register(IQueryService, QueryService)
    if not Container.is_registered(ITickerService):
        Container.register(ITickerService, TickerService)
    if not Container.is_registered(IRAGService):
        Container.register(IRAGService, RAGService)
    if not Container.is_registered(IChatService):
        # Register ChatService with explicit manager injection
        def create_chat_service() -> ChatService:
            """Create a ChatService instance with explicit dependencies."""
            query_service = Container.resolve(IQueryService)
            rag_service = Container.resolve(IRAGService)
            session_service = SessionService()
            history_service = get_chat_history_service()

            msg_manager = MessageManager(session_service)
            ctx_manager = ContextManager(query_service, rag_service)

            primary_llm = ChatOpenAI(
                model=settings.chatbot_model,
                temperature=settings.chatbot_temperature,
                streaming=True,
                api_key=settings.freellmapi_key or "dummy-key",
                base_url=settings.freellmapi_base_url,
                stream_options={"include_usage": True},
            )

            fallback_llm = ChatOpenAI(
                model=settings.chatbot_model,
                temperature=settings.chatbot_temperature,
                streaming=True,
                api_key=settings.openai_api_key,
                stream_options={"include_usage": True},
            )

            llm = primary_llm.with_fallbacks([fallback_llm]).bind_tools(
                [{"type": "web_search_preview"}]
            )

            resp_gen = ResponseGenerator(llm)

            return ChatService(
                llm=llm,
                message_manager=msg_manager,
                context_manager=ctx_manager,
                response_generator=resp_gen,
                history_service=history_service,
            )

        Container.register(IChatService, create_chat_service)


# Bootstrap on module load
_bootstrap_container()


@lru_cache
def get_query_service() -> IQueryService:
    """Get query service instance."""
    return Container.resolve(IQueryService)


@lru_cache
def get_ticker_service() -> ITickerService:
    """Get ticker service instance."""
    return Container.resolve(ITickerService)


@lru_cache
def get_rag_service() -> IRAGService:
    """Get RAG service instance."""
    return Container.resolve(IRAGService)


@lru_cache
def get_chat_service() -> IChatService:
    """Get chat service instance with RAG enabled."""
    return Container.resolve(IChatService)


@lru_cache
def get_user_upload_service() -> "UserUploadService":
    """Get UserUploadService instance."""
    openai_client = FallbackAsyncOpenAI(api_key=settings.openai_api_key)
    return UserUploadService(
        redis_client=get_async_redis(), openai_client=openai_client
    )


@lru_cache
def get_chat_history_service() -> ChatHistoryService:
    """Get chat-history service instance used for Redis hydration."""
    return ChatHistoryService()


@lru_cache
def get_research_service() -> ResearchReportCompiler:
    """Get ResearchReportCompiler instance."""
    return ResearchReportCompiler(
        openai_client=get_structured_llm_client(), redis_client=get_async_redis()
    )
