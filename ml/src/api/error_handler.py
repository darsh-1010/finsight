"""
FastAPI exception handlers.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.exceptions import (
    ChatbotException,
    DataSourceError,
    LLMError,
    QueryAnalysisError,
    RAGError,
    RateLimitError,
    ValidationError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup exception handlers for FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(LLMError)
    async def llm_exception_handler(_: Request, exc: LLMError) -> JSONResponse:
        logger.error(f"LLMError: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=502,  # Bad Gateway (Upstream LLM failure)
            content={
                "error": "LLMProviderError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(QueryAnalysisError)
    async def query_analysis_exception_handler(
        _: Request, exc: QueryAnalysisError
    ) -> JSONResponse:
        logger.error(f"QueryAnalysisError: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=422,  # Unprocessable Entity
            content={
                "error": "QueryAnalysisError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RAGError)
    async def rag_exception_handler(_: Request, exc: RAGError) -> JSONResponse:
        logger.error(f"RAGError: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=500,  # Internal Server Error
            content={
                "error": "RAGServiceError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ChatbotException)
    async def chatbot_exception_handler(
        _: Request, exc: ChatbotException
    ) -> JSONResponse:
        logger.error(f"ChatbotException: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=500,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DataSourceError)
    async def data_source_exception_handler(
        _: Request, exc: DataSourceError
    ) -> JSONResponse:
        logger.error(f"DataSourceError: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=503,  # Service Unavailable
            content={
                "error": "DataSourceError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_exception_handler(
        _: Request, exc: RateLimitError
    ) -> JSONResponse:
        logger.warning(f"RateLimitError: {exc.message}")
        return JSONResponse(
            status_code=429,
            content={
                "error": "RateLimitError",
                "message": exc.message,
                "retry_after": exc.details.get("retry_after", 60),
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        _: Request, exc: ValidationError
    ) -> JSONResponse:
        logger.warning(f"ValidationError: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "ValidationError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(f"RequestValidationError: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
