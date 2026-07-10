"""Test configuration and fixtures for RAG system tests."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, AsyncMock
from config.settings import QueryIntelligenceConfig as Settings


@pytest.fixture
def anyio_backend() -> str:
    """Force anyio tests onto asyncio in this environment."""
    return "asyncio"


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.weaviate_url = "http://localhost:8080"
    settings.openai_api_key = "test-key"
    settings.openai_embedding_model = "text-embedding-3-small"
    settings.chunk_size = 1000
    settings.chunk_overlap = 200
    settings.top_k_retrieval = 5
    settings.rerank_top_k = 3
    settings.session_ttl_seconds = 3600
    settings.redis_url = "redis://localhost:6379"
    return settings


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "url": "https://example.com/test-doc",
        "content": "This is a test document about financial markets. It contains information about stocks, bonds, and investment strategies. The document explains various financial concepts and provides examples of portfolio management.",
        "metadata": {"source_type": "web", "title": "Test Financial Document"},
    }


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return "What are the best investment strategies for beginners?"


@pytest.fixture
def mock_vector_store():
    """Mock vector store service."""
    mock_store = Mock()
    mock_store.search_similar = AsyncMock(
        return_value=[
            {
                "content": "Investment strategies for beginners include diversification and dollar-cost averaging.",
                "source_url": "https://example.com/investment-guide",
                "distance": 0.2,
                "score": 0.8,
            },
            {
                "content": "Portfolio management is crucial for long-term financial success.",
                "source_url": "https://example.com/portfolio-tips",
                "distance": 0.3,
                "score": 0.7,
            },
        ]
    )
    mock_store.store_document = AsyncMock(return_value=3)
    mock_store.delete_document = AsyncMock(return_value=True)
    mock_store.search_by_url = AsyncMock(return_value=[])
    mock_store.get_collection_stats = AsyncMock(return_value={"total_objects": 10})
    mock_store.close = Mock()
    return mock_store


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = "Based on the provided context, I recommend diversification and dollar-cost averaging as excellent investment strategies for beginners."
    mock_llm.invoke.return_value = mock_response
    return mock_llm


@pytest.fixture
def mock_session_manager():
    """Mock session manager."""
    mock_session = Mock()
    mock_session.generate_session_id.return_value = "test-session-123"
    mock_session.store_message = AsyncMock()
    mock_session.get_history = AsyncMock(
        return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you?"},
        ]
    )
    mock_session.clear_history = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session
