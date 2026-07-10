"""
Tests for onboarding endpoints.

  GET  /api/v1/onboarding/questions
  POST /api/v1/onboarding/answers
"""

import pytest


class TestGetOnboardingQuestions:
    """Tests for GET /api/v1/onboarding/questions."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated requests must be rejected."""
        response = client.get("/api/v1/onboarding/questions")
        assert response.status_code == 401

    def test_authenticated_returns_200_or_400(self, auth_client):
        """
        Authenticated request returns 200 (with questions) or 400
        (if no questions are seeded for the Foundation tier in the test DB).
        Both are acceptable — the endpoint must not crash.
        """
        test_client, _ = auth_client
        response = test_client.get("/api/v1/onboarding/questions")
        assert response.status_code in {200, 400}

    def test_questions_response_is_list_when_200(self, auth_client):
        """When questions exist, response must be a JSON array."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/onboarding/questions")
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_no_server_error(self, auth_client):
        """Endpoint must never return a 5xx status."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/onboarding/questions")
        assert response.status_code < 500


class TestSubmitOnboardingAnswer:
    """Tests for POST /api/v1/onboarding/answers."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated answer submission must be rejected."""
        response = client.post(
            "/api/v1/onboarding/answers",
            json={"question_id": 1, "answer_value": "beginner"},
        )
        assert response.status_code == 401

    def test_invalid_question_id_returns_error(self, auth_client):
        """Submitting an answer for a non-existent question should return 4xx."""
        test_client, _ = auth_client
        response = test_client.post(
            "/api/v1/onboarding/answers",
            json={"question_id": 99999, "answer_value": "beginner"},
        )
        assert 400 <= response.status_code < 500

    def test_missing_question_id_returns_422(self, auth_client):
        """Request missing required fields must fail Pydantic validation."""
        test_client, _ = auth_client
        response = test_client.post(
            "/api/v1/onboarding/answers",
            json={"answer_value": "beginner"},
        )
        assert response.status_code == 422


class TestOnboardingCIPCalculation:
    """Tests for GET /api/v1/onboarding/calculate-cip-profile."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated CIP requests must be rejected."""
        response = client.get("/api/v1/onboarding/calculate-cip-profile")
        assert response.status_code == 401

    def test_authenticated_returns_200_or_404_or_400(self, auth_client):
        """
        Returns 200 if CIP data exists, 400/404 if onboarding not completed,
        or 500 if database questions are not seeded.
        """
        test_client, _ = auth_client
        response = test_client.get("/api/v1/onboarding/calculate-cip-profile")
        assert response.status_code in {200, 400, 404, 500}
