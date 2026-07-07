"""
Core Pydantic schemas for the API.

Contains request and response models for all endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Chatbot Metadata Schemas
# ============================================================================


class MessageMetadata(BaseModel):
    """Structured metadata for a conversation message."""

    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the next turn",
    )

    model_config = {"extra": "allow"}


# ============================================================================
# Chatbot Schemas
# ============================================================================


class ConversationMessage(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant"] = Field(
        ...,
        description="Role of the message sender",
    )
    content: str = Field(
        ...,
        description="Message content",
    )
    timestamp: str | None = Field(
        None,
        description="ISO8601 timestamp when message was created",
    )
    metadata: MessageMetadata | None = Field(
        None,
        description="Optional structured metadata for the message",
    )


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history endpoint."""

    session_id: str = Field(..., description="Session identifier")
    messages: list[ConversationMessage] = Field(
        default_factory=list,
        description="Conversation messages in chronological order",
    )
    created_at: str | None = Field(
        None,
        description="ISO8601 timestamp when session was created",
    )
    turn_count: int = Field(
        default=0,
        description="Total number of conversation turns",
    )


class StreamEvent(BaseModel):
    """Event emitted during streaming response."""

    type: Literal[
        "session", "status", "sources", "content", "metadata", "error", "reasoning"
    ] = Field(
        ...,
        description="Type of stream event",
    )
    data: Any = Field(
        ...,
        description="Event data payload",
    )


class Source(BaseModel):
    """Provenance record for an external data source used in the response."""

    source: str = Field(..., description="Name of the source")
    source_type: str = Field(
        ..., description="Source type: 'yfinance', 'web', 'vectordb'"
    )
    ticker: str | None = Field(None, description="Stock ticker if applicable")
    data_type: str = Field(
        ..., description="Type of data cited (e.g., 'financial_data', 'news')"
    )
    url: str | None = Field(None, description="URL to source")
    id: str | None = Field(None, description="Source identifier")
    retrieved_at: str | None = Field(
        None, description="ISO8601 timestamp when data was retrieved"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class RequestMetadata(BaseModel):
    """Optional metadata attached to a request."""

    client_version: str | None = Field(None, description="Client application version")
    ui_channel: str | None = Field(None, description="UI channel (web, mobile, api)")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    user_message: str = Field(
        ...,
        description="User's chat message",
        min_length=1,
        max_length=5000,
    )
    session_id: str = Field(
        ...,
        description="Session ID for conversation continuity. Always provided by client.",
    )
    is_new: bool = Field(
        default=True,
        description="Indicates if this is a new session. If True, Redis context won't be fetched. Defaults to True.",
    )

    # --- Production fields (spec additions) ---
    request_id: str | None = Field(
        None,
        description="UUID for idempotency — echo back in response",
    )
    user_id: str | None = Field(
        None,
        description="User identifier for tracking and personalization",
    )
    tickers: list[str] | None = Field(
        None,
        description="Optional override: explicit ticker symbols to force-analyze. "
        "Usually omitted — the backend auto-extracts tickers from the message.",
    )
    include_rag: bool = Field(
        default=False,
        description="Whether to include RAG/Vector DB retrieval (future)",
    )
    max_response_tokens: int | None = Field(
        None,
        ge=50,
        le=4096,
        description="Maximum tokens for the response",
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="LLM temperature override for this request",
    )
    model: str | None = Field(
        None,
        description="Model override (e.g., 'gpt-5-mini')",
    )
    metadata: RequestMetadata | None = Field(
        None,
        description="Optional client metadata",
    )
    # --- Entitlement overrides (Internal/Fast-path) ---
    tier: int = Field(
        default=1,
        description="User tier level (0-5). Defaults to 1.",
    )
    tier_name: str | None = Field(
        None,
        description="Optional human-readable name for the tier",
    )
    features: dict[str, Any] | None = Field(
        None,
        description="Optional explicit entitlement overrides for the request",
    )
    file_ids: list[str] | None = Field(
        None,
        description="Optional: list of OpenAI file IDs to attach to this specific prompt",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_message": "What do you think about Tesla stock?",
                "session_id": "user-123-session",
                "is_new": True,
                "tier": 1,
                "user_id": "user_prod_001",
            }
        }
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    assistant_message: str = Field(..., description="Assistant's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    conversation_id: str | None = Field(
        None,
        description="Alias for session_id (chatbot-standard naming)",
    )
    # citations field removed, replaced by sources
    intent: str | None = Field(None, description="Inferred user intent")
    ticker: str | None = Field(None, description="Primary ticker symbol if applicable")
    chart: dict | None = Field(None, description="Chart configuration for UI")
    tokens_used: int | None = Field(
        None,
        description="Number of tokens used",
    )
    usage: dict[str, Any] | None = Field(
        None,
        description="Detailed token usage breakdown",
    )
    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions",
    )

    # --- Production fields (spec additions) ---
    request_id: str | None = Field(
        None,
        description="Echo of the request_id for correlation",
    )
    timestamp: str | None = Field(
        None,
        description="ISO8601 timestamp of the response",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Provenance: all external data sources used with URLs and timestamps",
    )
    confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Model's self-estimated confidence (0-1)",
    )
    latency_ms: int | None = Field(
        None,
        description="Total request processing time in milliseconds",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings (e.g., partial data, ambiguous ticker)",
    )
    error: str | None = Field(
        None,
        description="Error message if request partially failed",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assistant_message": "Tesla (TSLA) is currently trading at $245.30...",
                "session_id": "user-123-session",
                "conversation_id": "user-123-session",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "sources": [
                    {
                        "source": "Yahoo Finance",
                        "source_type": "yfinance",
                        "ticker": "TSLA",
                        "data_type": "price",
                        "id": "TSLA",
                        "url": "https://finance.yahoo.com/quote/TSLA",
                        "retrieved_at": "2026-02-10T12:00:00Z",
                        "confidence": 0.95,
                    }
                ],
                "tokens_used": 450,
                "latency_ms": 1230,
                "confidence": 0.92,
            }
        }
    )
