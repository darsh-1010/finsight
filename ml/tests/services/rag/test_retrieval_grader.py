"""Tests for the retrieval grader."""

from unittest.mock import MagicMock

import pytest

from src.services.rag.retrieval_grader import GradeResult, RetrievalGrader


class TestGradeResult:
    """Tests for the GradeResult schema."""

    def test_relevant_result(self):
        result = GradeResult(relevant=True, reason="Contains revenue data for the query.")
        assert result.relevant is True

    def test_irrelevant_result(self):
        result = GradeResult(relevant=False, reason="Discusses a different company.")
        assert result.relevant is False


class TestRetrievalGrader:
    """Tests for the RetrievalGrader service."""

    @pytest.mark.asyncio
    async def test_grade_and_filter_empty_input(self):
        """Should return empty list for empty input."""
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = MagicMock()
        grader._grader = MagicMock()
        result = await grader.grade_and_filter("test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_grade_and_filter_keeps_relevant(self):
        """Should keep chunks graded as relevant."""
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = MagicMock()

        # Mock the grader to return relevant for first, irrelevant for second.
        async def mock_grade(query, chunk):
            if "Apple revenue" in chunk.get("content", ""):
                return GradeResult(relevant=True, reason="Contains Apple revenue data.")
            return GradeResult(relevant=False, reason="Unrelated content.")

        grader._grade_single = mock_grade

        chunks = [
            {"content": "Apple revenue grew 15% YoY", "score": 0.9},
            {"content": "The weather in Tokyo was sunny", "score": 0.7},
        ]

        result = await grader.grade_and_filter("What is Apple's revenue?", chunks)
        assert len(result) == 1
        assert "Apple revenue" in result[0]["content"]

    @pytest.mark.asyncio
    async def test_grade_and_filter_fallback_on_all_filtered(self):
        """Should return highest-scored chunk if all are filtered."""
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = MagicMock()

        async def mock_grade(query, chunk):
            return GradeResult(relevant=False, reason="Not relevant.")

        grader._grade_single = mock_grade

        chunks = [
            {"content": "Low score chunk", "score": 0.3},
            {"content": "Higher score chunk", "score": 0.8},
        ]

        result = await grader.grade_and_filter("test", chunks)
        # Should return the highest-scored as fallback.
        assert len(result) == 1
        assert result[0]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_grade_chunks_fail_open_on_error(self):
        """Should assume relevant when grading fails (fail-open)."""
        grader = RetrievalGrader.__new__(RetrievalGrader)
        grader._llm = MagicMock()

        async def mock_grade(query, chunk):
            raise RuntimeError("LLM timeout")

        grader._grade_single = mock_grade

        chunks = [{"content": "Some content", "score": 0.7}]
        result = await grader.grade_chunks("test", chunks)

        assert len(result) == 1
        assert result[0]["_grade"]["relevant"] is True
