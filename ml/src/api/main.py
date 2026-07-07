"""
FastAPI Application Entry Point.

Production-ready API for financial query intelligence and chatbot services.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from config.settings import settings
from src.api.error_handler import setup_exception_handlers
from src.api.health import (APP_VERSION, build_liveness_report,
                            build_readiness_report,
                            start_openai_canary_monitor,
                            stop_openai_canary_monitor)
from src.api.middleware.quota_middleware import QuotaMiddleware
from src.api.routes import chatbot, market_insights, scraper, uploads
from src.llm.prompts import PromptLoader
from src.services.market_insights.weekly_compiler import WeeklySummaryCompiler
from src.utils.logger import get_logger, setup_logging
from src.utils.rate_limiter import RateLimiter, RateLimitError
from src.utils.redis_client import get_async_redis

logger = get_logger(__name__)


async def _warm_weekly_reports_cache() -> None:
    """Pre-compiles and warms weekly report caches for all tiers at startup."""
    try:
        logger.info(
            "[STARTUP_CACHE_WARMING] Initializing weekly insights pre-compilation background worker"
        )
        redis_client = get_async_redis()
        compiler = WeeklySummaryCompiler(redis_client=redis_client)

        for tier_id in (1, 2, 3, 4):
            cache_key = f"mi:weekly_report:tier:{tier_id}"
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    logger.info(
                        "[STARTUP_CACHE_WARMING] Tier %d cache is already warm.",
                        tier_id,
                    )
                    continue
            except (ConnectionError, OSError, ValueError, RuntimeError) as exc:
                logger.warning(
                    "[STARTUP_CACHE_WARMING_READ_ERROR] Redis read failed for Tier %d: %s",
                    tier_id,
                    exc,
                )

            logger.info(
                "[STARTUP_CACHE_WARMING_START] Warming cache for Subscription Tier: %d",
                tier_id,
            )
            try:
                await compiler.generate_and_cache_summary(
                    user_id="startup_cache_warmer", raw_alerts=[], user_tier=tier_id
                )
                logger.info(
                    "[STARTUP_CACHE_WARMING_SUCCESS] Tier %d successfully warmed.",
                    tier_id,
                )
            except (
                ConnectionError,
                OSError,
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
            ) as exc:
                logger.error(
                    "[STARTUP_CACHE_WARMING_ERROR] Tier %d warming failed: %s",
                    tier_id,
                    exc,
                )

        await redis_client.aclose()

    except (
        ConnectionError,
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
    ) as exc:
        logger.error(
            "[STARTUP_CACHE_WARMING_FAILED] Global pre-compilation failed: %s", exc
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    setup_logging()

    PromptLoader.pre_load_all()

    scraper.load_website_id_map()
    await start_openai_canary_monitor()
    logger.info("Starting Financial Intelligence API")

    # Run cache warming in a background task
    asyncio.create_task(_warm_weekly_reports_cache())

    yield

    # Shutdown
    await stop_openai_canary_monitor()
    logger.info("Shutting down Financial Intelligence API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="Financial Intelligence API",
        description="Production-ready API for financial query intelligence and chatbot services",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # Quota middleware (Tier enforcement)
    application.add_middleware(QuotaMiddleware)

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware (applied to chat endpoints)

    rate_limiter = RateLimiter(
        requests_per_minute=settings.rate_limit_rpm,
        tokens_per_minute=settings.rate_limit_tpm,
    )

    @application.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Only rate-limit chat endpoints
        if request.url.path.startswith("/api/v1/chat"):
            client_identity = _build_rate_limit_identity(request)
            try:
                await rate_limiter.acquire(client_identity, route=request.url.path)
            except RateLimitError as exc:
                logger.warning(
                    "Rate limit exceeded for %s | retry_after=%s",
                    _mask_identifier(client_identity),
                    exc.retry_after_seconds,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded. Please try again shortly.",
                        "retry_after_seconds": exc.retry_after_seconds,
                    },
                )
        return await call_next(request)

    # Request logging middleware
    @application.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration:.3f}s"
        )

        return response

    # Setup exception handlers
    setup_exception_handlers(application)

    # Register routes
    application.include_router(
        chatbot.router,
        prefix="/api/v1/chat",
        tags=["Chat"],
    )

    application.include_router(
        scraper.router,
        prefix="/api/v1",
        tags=["Scraper & RAG"],
    )

    application.include_router(
        uploads.router,
        prefix="/api/v1",
        tags=["Uploads"],
    )

    application.include_router(
        market_insights.router,
        prefix="/api/v1",
        tags=["Market Insights"],
    )

    # Health check endpoint
    @application.get("/health/live", tags=["Health"])
    async def health_live():
        return build_liveness_report()

    @application.get("/health/ready", tags=["Health"])
    async def health_ready():
        status_code, payload = await build_readiness_report()
        return JSONResponse(status_code=status_code, content=payload)

    @application.get("/health", tags=["Health"])
    async def health_check():
        status_code, payload = await build_readiness_report()
        return JSONResponse(status_code=status_code, content=payload)

    @application.get("/", tags=["Root"])
    async def root():
        return {
            "message": "Financial Intelligence API",
            "docs": "/docs",
            "health": "/health/ready",
            "live": "/health/live",
        }

    _configure_openapi_upload_schema_compat(application)

    return application


def _configure_openapi_upload_schema_compat(application: FastAPI) -> None:
    """Patch upload schema for Swagger file-picker compatibility."""

    def custom_openapi():
        if application.openapi_schema:
            return application.openapi_schema

        openapi_schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
        )
        components = openapi_schema.get("components", {}).get("schemas", {})
        upload_body_schema = components.get("Body_upload_documents_api_v1_upload_post")
        if upload_body_schema:
            files_schema = upload_body_schema.get("properties", {}).get("files")
            if files_schema and isinstance(files_schema.get("items"), dict):
                files_schema["items"] = {
                    "type": "string",
                    "format": "binary",
                }
        application.openapi_schema = openapi_schema
        return application.openapi_schema

    application.openapi = custom_openapi


def _build_rate_limit_identity(request: Request) -> str:
    """Build a stable request identity for shared rate limiting."""
    for header_name in ("x-user-id", "x-api-key"):
        value = request.headers.get(header_name)
        if value:
            return value.strip()

    client_host = request.client.host if request.client else "unknown"
    return client_host


def _mask_identifier(identifier: str) -> str:
    """Mask an identifier so logs do not expose raw client values."""
    if len(identifier) <= 8:
        return identifier
    return f"{identifier[:4]}***{identifier[-2:]}"


# Create the application instance
app = create_app()


def main() -> None:
    """Run the API with Uvicorn."""
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
