"""Tests for the reactive-decision / pump-and-dump risk nudges in ChatService.

Both nudges are heuristics over the FinancialContext(s) QueryService already resolves for
the turn - no new LLM call or data fetch - so they're tested directly against
`_build_risk_nudges`, plus one end-to-end test confirming a nudge actually reaches the
LLM's message list.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.chat.context_manager import ContextManager
from src.services.chat.history_service import ChatHistoryService
from src.services.chat.message_manager import MessageManager
from src.services.chat.response_generator import ResponseGenerator
from src.services.chat_service import ChatService, _build_risk_nudges


def _context(**overrides: object) -> dict:
    base = {
        "ticker": "AAPL",
        "price_change_pct": 0.0,
        "market_cap": 2_000_000_000_000,
        "volume": 1_000_000,
        "avg_volume": 1_000_000,
        "pe_ratio": 30.0,
        "forward_pe": 28.0,
    }
    base.update(overrides)
    return base


def _analysis(*contexts: dict) -> dict:
    return {"expansion": {}, "contexts": list(contexts)}


def test_no_nudge_for_calm_message_after_big_move() -> None:
    """A big move alone, without reactive language, should not trigger a nudge."""
    analysis = _analysis(_context(price_change_pct=-8.0))
    nudges = _build_risk_nudges("What is AAPL's revenue this quarter?", analysis)
    assert not nudges


def test_panic_nudge_fires_for_reactive_language_after_big_move() -> None:
    """Reactive buy/sell language after a >5% move should trigger the panic nudge."""
    analysis = _analysis(_context(price_change_pct=-8.0))
    nudges = _build_risk_nudges("Should I sell AAPL right now?", analysis)
    assert len(nudges) == 1
    assert "reactive buy/sell decision" in nudges[0]
    assert "AAPL" in nudges[0]


def test_panic_nudge_does_not_fire_below_move_threshold() -> None:
    """Reactive language on a small (<5%) move should not trigger the panic nudge."""
    analysis = _analysis(_context(price_change_pct=-2.0))
    nudges = _build_risk_nudges("Should I sell AAPL right now?", analysis)
    assert not nudges


def test_pump_and_dump_nudge_fires_for_illiquid_microcap_with_no_fundamentals() -> None:
    """Microcap + volume spike + no P/E data should trigger the hype-pattern nudge."""
    analysis = _analysis(
        _context(
            ticker="SHEL",
            price_change_pct=0.0,
            market_cap=50_000_000,
            volume=5_000_000,
            avg_volume=500_000,
            pe_ratio=None,
            forward_pe=None,
        )
    )
    nudges = _build_risk_nudges("What do you think of SHEL?", analysis)
    assert len(nudges) == 1
    assert "hype/pump-and-dump" in nudges[0]
    assert "SHEL" in nudges[0]


def test_no_pump_and_dump_nudge_for_normal_large_cap() -> None:
    """A normal large-cap ticker with real fundamentals should never trigger the flag."""
    analysis = _analysis(_context())
    nudges = _build_risk_nudges("What do you think of AAPL?", analysis)
    assert not nudges


def test_no_nudges_without_contexts() -> None:
    """No resolved ticker context means nothing to evaluate."""
    assert _build_risk_nudges("Should I sell everything?", {"expansion": {}, "contexts": []}) == []
    assert _build_risk_nudges("Should I sell everything?", None) == []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_msg_manager() -> MagicMock:
    manager = MagicMock(spec=MessageManager)
    manager.get_session_state.return_value = {}
    manager.enrich_query.side_effect = lambda m, s: m
    manager.build_context_summary.return_value = ""
    manager.update_history = AsyncMock()
    manager.update_session_after_turn = AsyncMock()
    return manager


@pytest.fixture
def mock_history_service() -> MagicMock:
    service = MagicMock(spec=ChatHistoryService)
    service.get_history_messages = AsyncMock(return_value=[])
    return service


@pytest.mark.anyio
async def test_panic_nudge_reaches_llm_messages(
    mock_msg_manager: MagicMock,
    mock_history_service: MagicMock,
) -> None:
    """End-to-end: a reactive question after a big drop should add a system nudge to the
    message list actually sent to the LLM."""
    analysis_result = {
        "expansion": {
            "intent": "investment_decision",
            "is_financial": True,
            "is_safe": True,
            "refusal_message": None,
            "suggested_follow_ups": [],
        },
        "contexts": [_context(price_change_pct=-9.0)],
    }
    from src.services.chat.domain_guard import DomainDecision

    mock_ctx_manager = MagicMock(spec=ContextManager)
    mock_ctx_manager.query_service = MagicMock()
    mock_fast_llm = MagicMock()
    mock_classifier = MagicMock()
    mock_classifier.ainvoke = AsyncMock(
        return_value=DomainDecision(is_financial=True, confidence=1.0, reason="Safe")
    )
    mock_fast_llm.with_structured_output.return_value = mock_classifier
    mock_ctx_manager.query_service._fast_llm = mock_fast_llm
    mock_ctx_manager.get_context = AsyncMock(
        return_value=("AAPL context", [], False, analysis_result, None, [])
    )

    mock_resp_gen = MagicMock(spec=ResponseGenerator)
    mock_resp_gen.generate = AsyncMock(return_value=("Here's the data.", {"total_tokens": 50}))

    service = ChatService(
        llm=MagicMock(),
        message_manager=mock_msg_manager,
        context_manager=mock_ctx_manager,
        response_generator=mock_resp_gen,
        history_service=mock_history_service,
    )

    await service.chat(message="Should I sell AAPL now?!", session_id="session-risk-1")

    messages = mock_resp_gen.generate.call_args.args[0]
    assert any("reactive buy/sell decision" in getattr(m, "content", "") for m in messages)
