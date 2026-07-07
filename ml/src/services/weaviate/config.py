"""Configuration constants for Weaviate service."""

from config.settings import settings

# ============================================================================
# Batch Configuration
# ============================================================================
# Use settings values which default to extremely safe values for stability
BATCH_SIZE = settings.weaviate_batch_size
BATCH_WORKERS = settings.weaviate_batch_workers

# Retry settings
BATCH_TIMEOUT_RETRIES = 3
BATCH_CONNECTION_ERROR_RETRIES = 5
RETRY_DELAY_INITIAL = 1.0  # Initial delay in seconds
RETRY_DELAY_MAX = 10.0  # Max delay in seconds
RETRY_DELAY_BACKOFF = 2.0  # Backoff factor

# ============================================================================
# Timeouts (in seconds)
# ============================================================================
GRPC_TIMEOUT = settings.weaviate_grpc_timeout
HTTP_TIMEOUT = settings.weaviate_http_timeout
STARTUP_TIMEOUT = 60

# ============================================================================
# Embedding Configuration
# ============================================================================
# OpenAI has strict token limits per request (8192 tokens)
# Batch size for embedding generation must be small enough to fit within limits
EMBEDDING_BATCH_SIZE = 20

# ============================================================================
# Collection Configuration
# ============================================================================
COLLECTION_NAME = "DocumentChunks"
