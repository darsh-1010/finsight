from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.chat.context_manager import ContextManager
from src.services.chat.history_service import ChatHistoryService
from src.services.chat.message_manager import MessageManager
from src.services.chat.response_generator import ResponseGenerator
from src.services.chat_service import ChatService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_msg_manager() -> MagicMock:
    manager = MagicMock(spec=MessageManager)
    manager.get_session_state.return_value = {}
    manager.enrich_query.side_effect = lambda m, s: m
    manager.build_context_summary.return_value = ""
    manager.get_history_messages.return_value = []
    manager.get_raw_history.return_value = []
    return manager


@pytest.fixture
def mock_ctx_manager() -> MagicMock:
    manager = MagicMock(spec=ContextManager)
    manager.query_service = MagicMock()
    manager.query_service._fast_llm = MagicMock()
    manager.query_service._fast_llm.ainvoke = AsyncMock()
    manager.query_service.analyze = AsyncMock()
    manager.get_context = AsyncMock(
        return_value=("Test Context", [], False, {"expansion": {"intent": "test"}})
    )
    return manager


@pytest.fixture
def mock_resp_gen() -> MagicMock:
    gen = MagicMock(spec=ResponseGenerator)
    gen.generate = AsyncMock(return_value=("Test Response", {"total_tokens": 10}))
    return gen


@pytest.fixture
def mock_history_service() -> MagicMock:
    service = MagicMock(spec=ChatHistoryService)
    service.get_history_messages = AsyncMock(return_value=[])
    return service


@pytest.mark.anyio
async def test_chat_orchestration(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    response = await service.chat(message="Hello", session_id="test-session")

    assert response["assistant_message"] == "Test Response"
    mock_ctx_manager.get_context.assert_called_once()
    mock_resp_gen.generate.assert_called_once()
    mock_msg_manager.update_history.assert_called_once()
    mock_msg_manager.update_session_after_turn.assert_called_once()


@pytest.mark.anyio
async def test_chat_error_handling(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    mock_ctx_manager.get_context.side_effect = Exception("Context error")

    with pytest.raises(Exception) as exc:
        await service.chat(message="Hello", session_id="test-session")

    assert "Context error" in str(exc.value)


@pytest.mark.anyio
async def test_chat_loads_history_for_existing_session(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    await service.chat(message="Hello", session_id="test-session", is_new=False)

    assert mock_history_service.get_history_messages.call_count >= 1


@pytest.mark.anyio
async def test_stream_awaits_prepare_messages(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    async def fake_stream(messages):
        assert isinstance(messages, list)
        yield {"type": "content", "data": "Hello"}
        yield {"type": "complete_text", "data": "Hello"}

    mock_resp_gen.stream.side_effect = fake_stream

    events = []
    async for event in service.stream(message="Hello", session_id="test-session"):
        events.append(event)

    assert any(event["type"] == "content" for event in events)
    mock_resp_gen.stream.assert_called_once()


@pytest.mark.anyio
async def test_is_identity_query(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    # Valid identity queries
    assert service._is_identity_query("who are you") is True
    assert service._is_identity_query("who are you???") is True
    assert service._is_identity_query("WHAT CAN YOU DO") is True
    assert service._is_identity_query("explain to me about yourself") is True
    assert service._is_identity_query("tell me about your features.") is True

    # Invalid queries
    assert service._is_identity_query("what is Apple's current price?") is False
    assert service._is_identity_query("who is the CEO of Microsoft?") is False
    assert service._is_identity_query("explain compound interest") is False


@pytest.mark.anyio
async def test_chat_identity_interception(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    response = await service.chat(message="who are you", session_id="identity-test")

    # Should directly return the capability explanation, skipping LLM & RAG calls
    assert "AI-based Financial Research & Wealth" in response["assistant_message"]
    assert response["intent"] == "explain_bot_capabilities"
    mock_ctx_manager.get_context.assert_not_called()
    mock_resp_gen.generate.assert_not_called()
    mock_msg_manager.update_history.assert_called_once()


@pytest.mark.anyio
async def test_stream_identity_interception(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    events = []
    async for event in service.stream(
        message="explain about yourself",
        session_id="stream-identity-test"
    ):
        events.append(event)

    # Validate correct session and block events
    assert any(e["type"] == "session" for e in events)
    assert any(e["type"] == "content_block_delta" for e in events)

    complete_events = [e for e in events if e["type"] == "complete_text"]
    assert len(complete_events) == 1
    assert "AI-based Financial Research & Wealth" in complete_events[0]["data"]

    # Validate final metadata event
    metadata_events = [e for e in events if e["type"] == "metadata"]
    assert len(metadata_events) == 1
    metadata = metadata_events[0]["data"]
    assert "What is your quantitative risk tier?" in metadata["suggested_follow_ups"]

    mock_ctx_manager.get_context.assert_not_called()
    mock_resp_gen.stream.assert_not_called()


@pytest.mark.anyio
async def test_direct_llm_only_chat_fast_path(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    from src.core.tier_policy import TierFeatures
    mock_features = TierFeatures(
        name="Tier 0 (Guest)",
        search_depth=0,
        has_web_access=False,
        max_tokens=768,
        prompt_profile="guest",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=True,
        quota_daily_requests=10,
        model_name="test-model",
    )

    # Test with a ticker
    response = await service.chat(
        message="What is the price of TSLA?",
        session_id="direct-llm-test",
        features=mock_features,
    )

    # 1. Verify get_context and query analysis are bypassed
    mock_ctx_manager.get_context.assert_not_called()
    # 2. Verify response generator is still called
    mock_resp_gen.generate.assert_called_once()
    # 3. Verify response fields and follow-ups are returned
    assert response["assistant_message"] == "Test Response"
    assert "TSLA" in response["suggested_follow_ups"][0]

    # Test with personal finance keywords
    mock_resp_gen.generate.reset_mock()
    response_pf = await service.chat(
        message="how to save for retirement",
        session_id="direct-llm-test-pf",
        features=mock_features,
    )
    assert response_pf["assistant_message"] == "Test Response"
    assert "Roth IRA" in response_pf["suggested_follow_ups"][1]


@pytest.mark.anyio
async def test_direct_llm_only_stream_fast_path(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    from src.core.tier_policy import TierFeatures
    mock_features = TierFeatures(
        name="Tier 0 (Guest)",
        search_depth=0,
        has_web_access=False,
        max_tokens=768,
        prompt_profile="guest",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=True,
        quota_daily_requests=10,
        model_name="test-model",
    )

    async def fake_stream(messages, **kwargs):
        yield {"type": "content", "data": "Streaming response"}
        yield {"type": "complete_text", "data": "Streaming response"}

    mock_resp_gen.stream.side_effect = fake_stream

    events = []
    async for event in service.stream(
        message="what is Apple's valuation?",
        session_id="direct-llm-stream-test",
        features=mock_features,
    ):
        events.append(event)

    # 1. Verify get_context is bypassed
    mock_ctx_manager.get_context.assert_not_called()
    # 2. Verify response generator stream is called
    mock_resp_gen.stream.assert_called_once()

    # 3. Verify events returned
    assert any(e["type"] == "session" for e in events)
    assert any(e["type"] == "content" for e in events)

    # 4. Verify final metadata has follow-ups
    metadata_events = [e for e in events if e["type"] == "metadata"]
    assert len(metadata_events) == 1
    metadata = metadata_events[0]["data"]
    assert "AAPL" in metadata["suggested_follow_ups"][0]


@pytest.mark.anyio
async def test_guardrail_layer1_regex_blocking(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    # Obvious off-domain query: "explain machine learning"
    response = await service.chat(message="explain machine learning", session_id="regex-block-test")

    # Should block immediately with the warm redirect refusal message
    assert "falls outside my area of expertise" in response["assistant_message"]
    mock_ctx_manager.get_context.assert_not_called()
    mock_resp_gen.generate.assert_not_called()


@pytest.mark.anyio
async def test_guardrail_layer1_regex_financial_override(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    # Question about ML but with financial override context:
    # "How does machine learning affect stock trading algorithms?"
    # Should not block at Layer 1 regex.
    response = await service.chat(
        message="How does machine learning affect stock trading algorithms?",
        session_id="regex-override-test"
    )

    # Verified: RAG and context pipelines should run
    assert response["assistant_message"] == "Test Response"
    mock_ctx_manager.get_context.assert_called_once()
    mock_resp_gen.generate.assert_called_once()


@pytest.mark.anyio
async def test_guardrail_layer2_fast_llm_blocking(
    mock_llm: MagicMock,
    mock_msg_manager: MagicMock,
    mock_ctx_manager: MagicMock,
    mock_resp_gen: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    service = ChatService(
        llm=mock_llm,
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    from src.core.tier_policy import TierFeatures
    mock_features = TierFeatures(
        name="Tier 0 (Guest)",
        search_depth=0,
        has_web_access=False,
        max_tokens=768,
        prompt_profile="guest",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=True,
        quota_daily_requests=10,
        model_name="test-model",
    )

    mock_query_service = MagicMock()
    mock_fast_llm = MagicMock()
    mock_classifier = MagicMock()
    
    from src.services.chat.domain_guard import DomainDecision, DomainGuard
    decision = DomainDecision(is_financial=False, confidence=0.9, reason="Reject")
    mock_classifier.ainvoke = AsyncMock(return_value=decision)
    mock_fast_llm.with_structured_output.return_value = mock_classifier
    mock_query_service._fast_llm = mock_fast_llm
    
    service.context_manager.query_service = mock_query_service
    service._domain_guard = DomainGuard(fast_llm=mock_fast_llm, history_service=service.history_service)

    # Nuanced off-domain query that gets through Layer 1 regex, e.g. "tell me how to debug code"
    response = await service.chat(
        message="tell me how to debug code",
        session_id="fast-llm-block-test",
        features=mock_features,
    )

    # Should be blocked at Layer 2 fast LLM check
    assert "falls outside my area of expertise" in response["assistant_message"]
    mock_resp_gen.generate.assert_not_called()


