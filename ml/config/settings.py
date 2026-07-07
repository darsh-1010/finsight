"""
Configuration for the Financial Intelligence system.
"""

from dotenv import load_dotenv
load_dotenv()

import os
from pathlib import Path
from typing import Any, Iterable

import yaml

from pydantic import BaseModel, Field


def _load_env_int(
    env_names: Iterable[str],
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Load the first valid integer from environment variables."""
    for env_name in env_names:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            continue

        try:
            parsed_value = int(raw_value)
        except (TypeError, ValueError):
            continue

        if minimum is not None:
            parsed_value = max(parsed_value, minimum)
        if maximum is not None:
            parsed_value = min(parsed_value, maximum)
        return parsed_value

    return default


def _load_retrieval_config() -> dict[str, Any]:
    """Load retrieval configuration from YAML file with environment variable overrides."""
    config_path = Path(__file__).parent / "retrieval_config.yaml"
    config: dict[str, Any] = {}

    # Load defaults from YAML file
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Override with environment variables if set
    env_overrides = {
        "min_article_relevance_score": os.getenv("MIN_ARTICLE_RELEVANCE_SCORE"),
        "min_document_relevance_score": os.getenv("MIN_DOCUMENT_RELEVANCE_SCORE"),
        "rerank_top_k": os.getenv("RERANK_TOP_K"),
    }

    for key, value in env_overrides.items():
        if value is not None:
            try:
                config[key] = float(value) if key != "rerank_top_k" else int(value)
            except (ValueError, TypeError):
                pass  # Keep default if conversion fails

    return config


class QueryIntelligenceConfig(BaseModel):
    """Configuration for query intelligence components."""

    # =========================================================================
    # LLM Models (model-specific environment variables)
    # =========================================================================
    gpt_5_mini: str = Field(
        default_factory=lambda: os.getenv("GPT_5_MINI", "gpt-5-mini"),
        description="GPT-5 Mini model identifier",
    )
    gpt_4_1: str = Field(
        default_factory=lambda: os.getenv("GPT_4_1", "gpt-4.1"),
        description="GPT-4.1 model identifier",
    )
    gpt_4o_mini: str = Field(
        default_factory=lambda: os.getenv("GPT_4O_MINI", "gpt-4.1-mini"),
        description="GPT-4o Mini model identifier",
    )

    # =========================================================================
    # Service-Specific Model Selection
    # =========================================================================
    chatbot_model: str = Field(
        default_factory=lambda: os.getenv(
            "CHATBOT_MODEL", os.getenv("GPT_4O_MINI", "gpt-4.1-mini")
        ),
        description="Model to use for chatbot service",
    )
    default_chat_confidence: float = Field(
        default_factory=lambda: float(os.getenv("DEFAULT_CHAT_CONFIDENCE", "0.9")),
        description="Default confidence score for chat responses",
    )
    query_analysis_model: str = Field(
        default_factory=lambda: os.getenv(
            "QUERY_ANALYSIS_MODEL", os.getenv("GPT_4_1", "gpt-4.1-mini")
        ),
        description="Model to use for query analysis",
    )
    ticker_resolution_model: str = Field(
        default_factory=lambda: os.getenv(
            "TICKER_RESOLUTION_MODEL", os.getenv("GPT_4O_MINI", "gpt-4.1-mini")
        ),
        description="Model to use for ticker resolution",
    )

    # =========================================================================
    # LLM Temperature Settings
    # =========================================================================
    chatbot_temperature: float = Field(
        default_factory=lambda: float(os.getenv("CHATBOT_TEMPERATURE", "0.7")),
        ge=0.0,
        le=2.0,
        description="Temperature for chatbot responses",
    )
    query_analysis_temperature: float = Field(
        default_factory=lambda: float(os.getenv("QUERY_ANALYSIS_TEMPERATURE", "0.1")),
        ge=0.0,
        le=2.0,
        description="Temperature for query analysis",
    )
    ticker_resolution_temperature: float = Field(
        default_factory=lambda: float(
            os.getenv("TICKER_RESOLUTION_TEMPERATURE", "0.0")
        ),
        ge=0.0,
        le=2.0,
        description="Temperature for ticker resolution",
    )

    # =========================================================================
    # Conversation and History Settings
    # =========================================================================
    max_conversation_history: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONVERSATION_HISTORY", "20")),
        ge=1,
        le=100,
        description="Maximum number of conversation turns to keep in history",
    )
    max_context_chars: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_CHARS", "12000")),
        ge=1000,
        le=50000,
        description="Maximum characters for LLM context",
    )

    # =========================================================================
    # Redis TTL Settings (in seconds)
    # =========================================================================
    redis_default_ttl: int = Field(
        default_factory=lambda: int(os.getenv("REDIS_DEFAULT_TTL_SECONDS", "86400")),
        description="Global default TTL for Redis keys if specific TTL is not set",
    )
    session_state_ttl: int = Field(
        default_factory=lambda: int(
            os.getenv(
                "SESSION_STATE_TTL_SECONDS",
                os.getenv("REDIS_DEFAULT_TTL_SECONDS", "2592000"),
            )
        ),
        ge=3600,
        description="TTL for session state in Redis (seconds)",
    )
    chat_history_ttl: int = Field(
        default_factory=lambda: int(os.getenv("CHAT_HISTORY_TTL_SECONDS", "259200")),
        ge=3600,
        description="TTL for chat history in Redis (seconds)",
    )
    ticker_cache_ttl: int = Field(
        default_factory=lambda: int(
            os.getenv(
                "TICKER_CACHE_TTL_SECONDS",
                os.getenv("REDIS_DEFAULT_TTL_SECONDS", "86400"),
            )
        ),
        ge=300,
        description="TTL for ticker cache in Redis (seconds)",
    )

    # =========================================================================
    # Ticker Resolution Settings
    # =========================================================================
    validate_tickers: bool = Field(
        default_factory=lambda: os.getenv("VALIDATE_TICKERS", "true").lower() == "true",
        description="Whether to validate tickers against yFinance",
    )
    max_parallel_resolutions: int = Field(
        default_factory=lambda: int(os.getenv("MAX_PARALLEL_RESOLUTIONS", "5")),
        ge=1,
        le=20,
        description="Max tickers to resolve in parallel",
    )
    ticker_high_confidence: float = Field(
        default_factory=lambda: float(os.getenv("TICKER_HIGH_CONFIDENCE", "0.85")),
        description="High confidence threshold for ticker resolution",
    )
    ticker_medium_confidence: float = Field(
        default_factory=lambda: float(os.getenv("TICKER_MEDIUM_CONFIDENCE", "0.6")),
        description="Medium confidence threshold for ticker resolution",
    )

    # =========================================================================
    # Session and History Limits
    # =========================================================================
    max_history_turns: int = Field(
        default_factory=lambda: int(os.getenv("MAX_HISTORY_TURNS", "20")),
        description="Maximum turns to keep in chat history",
    )
    max_message_retrieved: int = Field(
        default_factory=lambda: _load_env_int(
            ("MAX_MESSAGE_RETRIVED", "MAX_MESSAGE_RETRIEVED"),
            default=5,
            minimum=1,
            maximum=10,
        ),
        description="Maximum number of messages fetched from the backend fallback",
    )
    session_summary_max_chars: int = Field(
        default_factory=lambda: int(os.getenv("SESSION_SUMMARY_MAX_CHARS", "5000")),
        description="Maximum characters for session summary before truncation",
    )
    session_summary_keep_chars: int = Field(
        default_factory=lambda: int(os.getenv("SESSION_SUMMARY_KEEP_CHARS", "2000")),
        description="Characters to keep when truncating session summary",
    )

    # =========================================================================
    # Query Expansion Settings
    # =========================================================================
    max_expansions: int = Field(
        default_factory=lambda: int(os.getenv("MAX_EXPANSIONS", "8")),
        ge=1,
        le=20,
        description="Maximum number of query expansions to generate",
    )
    min_expansions: int = Field(
        default_factory=lambda: int(os.getenv("MIN_EXPANSIONS", "3")),
        ge=1,
        description="Minimum number of query expansions",
    )

    # =========================================================================
    # Data Fetching Settings
    # =========================================================================
    default_history_period: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_HISTORY_PERIOD", "1y"),
        description="Default time period for historical data",
    )
    include_financials: bool = Field(
        default_factory=lambda: os.getenv("INCLUDE_FINANCIALS", "true").lower()
        == "true",
        description="Whether to fetch financial statements by default",
    )
    include_recommendations: bool = Field(
        default_factory=lambda: os.getenv("INCLUDE_RECOMMENDATIONS", "true").lower()
        == "true",
        description="Whether to fetch analyst recommendations",
    )
    max_parallel_yfinance_fetches: int = Field(
        default_factory=lambda: int(os.getenv("MAX_PARALLEL_YFINANCE_FETCHES", "4")),
        ge=1,
        le=20,
        description="Maximum concurrent yFinance fetch operations",
    )
    yfinance_use_browser_session: bool = Field(
        default_factory=lambda: os.getenv(
            "YFINANCE_USE_BROWSER_SESSION", "true"
        ).lower()
        == "true",
        description="Whether to route yfinance through a browser-impersonated HTTP session",
    )
    yfinance_impersonate: str = Field(
        default_factory=lambda: os.getenv("YFINANCE_IMPERSONATE", "chrome"),
        description="Browser fingerprint target used by curl_cffi for yfinance requests",
    )
    yfinance_http_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("YFINANCE_HTTP_TIMEOUT_SECONDS", "20")),
        ge=5,
        le=60,
        description="Timeout for browser-impersonated yfinance requests",
    )

    # =========================================================================
    # Timeouts and Retries
    # =========================================================================
    request_timeout: int = Field(
        default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")),
        ge=5,
        le=120,
        description="Timeout for external API calls (seconds)",
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")),
        ge=0,
        le=5,
        description="Maximum retry attempts for failed requests",
    )
    retry_initial_delay: float = Field(
        default_factory=lambda: float(os.getenv("RETRY_INITIAL_DELAY", "1.0")),
        description="Initial delay between retries in seconds",
    )
    retry_max_delay: float = Field(
        default_factory=lambda: float(os.getenv("RETRY_MAX_DELAY", "8.0")),
        description="Maximum delay between retries",
    )

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_rpm: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_RPM", "60")),
        ge=1,
        description="Rate limit requests per minute",
    )
    rate_limit_window_seconds: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        ge=1,
        le=3600,
        description="Sliding window length for rate limiting",
    )
    rate_limit_tpm: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_TPM", "90000")),
        ge=1,
        description="Rate limit tokens per minute",
    )

    # =========================================================================
    # Security Settings
    # =========================================================================
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
            if origin.strip()
        ],
        description="Allowed CORS origins (comma-separated in ENV)",
    )

    # =========================================================================
    # Logging Settings
    # =========================================================================
    log_llm_calls: bool = Field(
        default_factory=lambda: os.getenv("LOG_LLM_CALLS", "false").lower() == "true",
        description="Whether to log full LLM request/response (verbose)",
    )

    # =========================================================================
    # Health Check Settings
    # =========================================================================
    health_openai_canary_interval_seconds: int = Field(
        default_factory=lambda: int(
            os.getenv("HEALTH_OPENAI_CANARY_INTERVAL_SECONDS", "60")
        ),
        ge=15,
        le=300,
        description="Interval for refreshing the cached OpenAI canary result",
    )
    health_openai_canary_timeout_seconds: int = Field(
        default_factory=lambda: int(
            os.getenv("HEALTH_OPENAI_CANARY_TIMEOUT_SECONDS", "10")
        ),
        ge=3,
        le=60,
        description="Timeout for the OpenAI canary request",
    )
    health_openai_canary_stale_after_seconds: int = Field(
        default_factory=lambda: int(
            os.getenv("HEALTH_OPENAI_CANARY_STALE_AFTER_SECONDS", "180")
        ),
        ge=30,
        le=900,
        description="Maximum age for the cached OpenAI canary result before readiness fails",
    )

    # =========================================================================
    # Weaviate Vector Store Settings
    # =========================================================================
    weaviate_url: str = Field(
        default_factory=lambda: os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        description="Weaviate instance URL",
    )
    weaviate_grpc_url: str = Field(
        default_factory=lambda: os.getenv("WEAVIATE_GRPC_URL", "localhost:50051"),
        description="Weaviate gRPC URL for Python client v4",
    )
    weaviate_api_key: str | None = Field(
        default_factory=lambda: os.getenv("WEAVIATE_API_KEY"),
        description="Optional Weaviate API key for authentication",
    )
    weaviate_batch_size: int = Field(
        default_factory=lambda: int(os.getenv("WEAVIATE_BATCH_SIZE", "5")),
        ge=1,
        le=100,
        description="Weaviate batch size for object creation",
    )
    weaviate_batch_workers: int = Field(
        default_factory=lambda: int(os.getenv("WEAVIATE_BATCH_WORKERS", "1")),
        ge=1,
        le=10,
        description="Number of workers for batch processing",
    )
    weaviate_grpc_timeout: int = Field(
        default_factory=lambda: int(os.getenv("WEAVIATE_GRPC_TIMEOUT", "180")),
        description="Weaviate gRPC timeout in seconds",
    )
    weaviate_http_timeout: int = Field(
        default_factory=lambda: int(os.getenv("WEAVIATE_HTTP_TIMEOUT", "120")),
        description="Weaviate HTTP timeout in seconds",
    )

    # =========================================================================
    # RAG Settings
    # =========================================================================
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        description="OpenAI embedding model for vector embeddings",
    )
    chunk_size: int = Field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1000")),
        ge=100,
        le=5000,
        description="Character count for document chunks",
    )
    max_document_chunk_chars: int = Field(
        default_factory=lambda: int(os.getenv("MAX_DOCUMENT_CHUNK_CHARS", "1000")),
        description="Maximum characters to show from a single document chunk in LLM context",
    )
    chunk_overlap: int = Field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "200")),
        ge=0,
        le=1000,
        description="Character overlap between chunks",
    )
    rerank_top_k: int = Field(
        default_factory=lambda: int(_load_retrieval_config().get("rerank_top_k", 5)),
        ge=1,
        le=20,
        description="Number of top documents to retrieve from vector store",
    )
    min_article_relevance_score: float = Field(
        default_factory=lambda: float(
            _load_retrieval_config().get("min_article_relevance_score", 0.45)
        ),
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity score for scraped article chunks",
    )
    min_document_relevance_score: float = Field(
        default_factory=lambda: float(
            _load_retrieval_config().get("min_document_relevance_score", 0.40)
        ),
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity score for document chunks",
    )

    # =========================================================================
    # PDF Scraper Settings
    # =========================================================================
    pdf_scraper_timeout: int = Field(
        default_factory=lambda: int(os.getenv("PDF_SCRAPER_TIMEOUT", "30")),
        ge=5,
        le=300,
        description="Timeout for PDF download in seconds",
    )
    pdf_min_content_length: int = Field(
        default_factory=lambda: int(os.getenv("PDF_MIN_CONTENT_LENGTH", "300")),
        ge=50,
        le=5000,
        description="Minimum character count for valid PDF content",
    )

    # =========================================================================
    # API Keys
    # =========================================================================
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", ""),
        description="OpenAI API key",
    )
    freellmapi_base_url: str = Field(
        default_factory=lambda: os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1"),
        description="FreeLLMAPI base URL",
    )
    freellmapi_key: str = Field(
        default_factory=lambda: os.getenv("FREELLMAPI_KEY", ""),
        description="FreeLLMAPI unified key",
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"),
        description="Redis connection URL",
    )
    ml_data_transfer_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "ML_DATA_TRANSFER_BASE_URL", "https://api.chatfinsight.ai"
        ),
        description="Base URL for the backend chat-history transfer API",
    )
    ml_data_transfer_token: str | None = Field(
        default_factory=lambda: os.getenv("ML_DATA_TRANSFER_TOKEN"),
        description="Token required by the backend chat-history transfer API",
    )
    redis_socket_connect_timeout_seconds: float = Field(
        default_factory=lambda: float(
            os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "3.0")
        ),
        ge=0.1,
        le=30.0,
        description="Redis connection timeout in seconds",
    )
    redis_socket_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "3.0")),
        ge=0.1,
        le=30.0,
        description="Redis socket timeout in seconds",
    )
    redis_health_check_interval_seconds: int = Field(
        default_factory=lambda: int(
            os.getenv("REDIS_HEALTH_CHECK_INTERVAL_SECONDS", "30")
        ),
        ge=0,
        le=300,
        description="Redis connection health-check interval",
    )
    redis_max_connections: int = Field(
        default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        ge=1,
        le=100,
        description="Maximum Redis connections for the client pool",
    )

    # =========================================================================
    # AWS S3 Configuration
    # =========================================================================
    aws_access_key_id: str | None = Field(
        default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID"),
        description="AWS Access Key ID",
    )
    aws_secret_access_key: str | None = Field(
        default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY"),
        description="AWS Secret Access Key",
    )
    aws_region: str = Field(
        default_factory=lambda: os.getenv("AWS_REGION", "eu-north-1"),
        description="AWS Region",
    )
    s3_bucket_name: str = Field(
        default_factory=lambda: os.getenv("S3_BUCKET_NAME", "finsight-staging"),
        description="Target S3 bucket for PDF storage",
    )

    # =========================================================================
    # Tier System Settings
    # =========================================================================
    tier_enforcement_enabled: bool = Field(
        default_factory=lambda: os.getenv("TIER_ENFORCEMENT_ENABLED", "true").lower()
        == "true",
        description="If False, all users get Tier 3 for smoke-testing. Set True in production.",
    )
    tier_features_cache_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("TIER_FEATURES_CACHE_TTL_SECONDS", "3600")),
        description="How long to cache tier feature contracts from backend (default: 1 hour).",
    )
    tier_0_quota: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_0_QUOTA", "3")),
        description="Daily request quota for Tier 0"
    )
    tier_1_quota: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_1_QUOTA", "10")),
        description="Daily request quota for Tier 1"
    )
    tier_2_quota: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_2_QUOTA", "50")),
        description="Daily request quota for Tier 2"
    )
    tier_3_quota: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_3_QUOTA", "250")),
        description="Daily request quota for Tier 3"
    )
    tier_4_quota: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_4_QUOTA", "1000")),
        description="Daily request quota for Tier 4"
    )

    tier_1_model: str = Field(
        default_factory=lambda: os.getenv("ML_TIER_1_MODEL", os.getenv("CHATBOT_MODEL", "gpt-4.1-mini")),
        description="Model to use for Tier 1 users"
    )
    tier_2_model: str = Field(
        default_factory=lambda: os.getenv("ML_TIER_2_MODEL", os.getenv("CHATBOT_MODEL", "gpt-4.1-mini")),
        description="Model to use for Tier 2 users"
    )
    tier_3_model: str = Field(
        default_factory=lambda: os.getenv("ML_TIER_3_MODEL", os.getenv("CHATBOT_MODEL", "gpt-4.1-mini")),
        description="Model to use for Tier 3 users"
    )
    tier_4_model: str = Field(
        default_factory=lambda: os.getenv("ML_TIER_4_MODEL", os.getenv("CHATBOT_MODEL", "gpt-4.1-mini")),
        description="Model to use for Tier 4 users"
    )

    tier_0_model: str = Field(
        default_factory=lambda: os.getenv("ML_TIER_0_MODEL", os.getenv("CHATBOT_MODEL", "gpt-4.1-mini")),
        description="Model to use for Tier 0 users"
    )

    # =========================================================================
    # Upload Settings
    # =========================================================================
    max_upload_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("ML_MAX_UPLOAD_SIZE_BYTES", "20971520")
        )  # 20MB
    )
    tier_3_max_upload_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("ML_TIER_3_MAX_UPLOAD_SIZE_BYTES", "10485760")
        )  # 10MB
    )
    tier_4_max_upload_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("ML_TIER_4_MAX_UPLOAD_SIZE_BYTES", os.getenv("ML_MAX_UPLOAD_SIZE_BYTES", "20971520"))
        )  # 20MB
    )
    user_upload_chunk_size: int = Field(
        default_factory=lambda: int(os.getenv("USER_UPLOAD_CHUNK_SIZE", "1500"))
    )
    user_upload_chunk_overlap: int = Field(
        default_factory=lambda: int(os.getenv("USER_UPLOAD_CHUNK_OVERLAP", "200"))
    )
    tier_3_max_docs_per_session: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_3_MAX_DOCS_PER_SESSION", "3"))
    )
    tier_4_max_docs_per_session: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_4_MAX_DOCS_PER_SESSION", "5"))
    )
    tier_3_max_files_per_request: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_3_MAX_FILES_PER_REQUEST", "3"))
    )
    tier_4_max_files_per_request: int = Field(
        default_factory=lambda: int(os.getenv("ML_TIER_4_MAX_FILES_PER_REQUEST", "8"))
    )
    max_document_tokens: int = Field(
        default_factory=lambda: int(os.getenv("ML_MAX_DOCUMENT_TOKENS", "50000"))
    )
    tier_3_max_document_tokens: int = Field(
        default_factory=lambda: int(
            os.getenv("ML_TIER_3_MAX_DOCUMENT_TOKENS", "35000")
        )
    )
    tier_4_max_document_tokens: int = Field(
        default_factory=lambda: int(
            os.getenv("ML_TIER_4_MAX_DOCUMENT_TOKENS", "45000")
        )
    )
    tier_3_token_budget_ratio: float = Field(
        default_factory=lambda: float(os.getenv("ML_TIER_3_TOKEN_BUDGET_RATIO", "0.25")),
        ge=0.01,
        le=1.0,
    )
    tier_4_token_budget_ratio: float = Field(
        default_factory=lambda: float(os.getenv("ML_TIER_4_TOKEN_BUDGET_RATIO", "0.35")),
        ge=0.01,
        le=1.0,
    )
    openai_file_id_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("OPENAI_FILE_ID_TTL_SECONDS", "86400"))
    )

    # =========================================================================
    # Quant Module Settings
    # =========================================================================
    quant_volatility_window_days: int = Field(
        default_factory=lambda: int(os.getenv("QUANT_VOLATILITY_WINDOW_DAYS", "30"))
    )

    model_config = {"extra": "forbid"}  # Strict config


# Default configuration instance - SINGLETON
settings = QueryIntelligenceConfig()
