"""Confirms QueryService, TickerService, RetrievalGrader, and CypherGenerator
build their default LLM via get_chat_model (litellm-backed) instead of a bare
ChatOpenAI() - these had no fallback behaviour at all before this swap.
"""

from unittest.mock import MagicMock, patch

from config.settings import settings


def test_retrieval_grader_uses_litellm_by_default():
    with patch("src.services.rag.retrieval_grader.get_chat_model") as mock_get_chat_model:
        mock_get_chat_model.return_value = MagicMock()
        from src.services.rag.retrieval_grader import RetrievalGrader

        RetrievalGrader()

    mock_get_chat_model.assert_called_once_with(settings.gpt_4o_mini, temperature=0.0)


def test_cypher_generator_uses_litellm_by_default():
    with patch(
        "src.services.knowledge_graph.cypher_generator.get_chat_model"
    ) as mock_get_chat_model:
        mock_get_chat_model.return_value = MagicMock()
        from src.services.knowledge_graph.cypher_generator import CypherGenerator

        CypherGenerator()

    mock_get_chat_model.assert_called_once_with(settings.gpt_4o_mini, temperature=0.0)


def test_ticker_service_uses_litellm_by_default():
    with patch("src.services.ticker_service.get_chat_model") as mock_get_chat_model, patch(
        "src.services.ticker_service.PromptLoader.load", return_value="prompt"
    ):
        mock_get_chat_model.return_value = MagicMock()
        from src.services.ticker_service import TickerService

        TickerService()

    mock_get_chat_model.assert_called_once_with(
        settings.ticker_resolution_model,
        temperature=settings.ticker_resolution_temperature,
    )


def test_query_service_uses_litellm_for_both_full_and_fast_models():
    with patch("src.services.query_service.get_chat_model") as mock_get_chat_model, patch(
        "src.services.query_service.PromptLoader.load", return_value="prompt"
    ):
        mock_get_chat_model.return_value = MagicMock()
        from src.services.query_service import QueryService

        QueryService()

    calls = [c.args[0] for c in mock_get_chat_model.call_args_list]
    assert settings.query_analysis_model in calls
    assert settings.gpt_4o_mini in calls
