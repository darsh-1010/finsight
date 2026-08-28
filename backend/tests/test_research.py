"""
Tests for the research report proxy endpoint.

  POST /api/v1/research/report

The ml service call is mocked — tests run fully offline.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from app.models.subscriptions import Subscription

MOCK_ML_REPORT = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "generated_at": "2026-08-24T00:00:00Z",
    "summary": "Apple is a stable technology company.",
    "valuation_take": "Fairly valued.",
    "growth_take": "Steady growth.",
    "risk_take": "Low risk.",
    "filing_highlights": [],
    "sources": [],
    "confidence": 0.8,
    "warnings": [],
    "from_cache": False,
}


def _mock_ml_client(status_code: int = 200, payload: dict | None = None):
    """Build a mock replacement for httpx.AsyncClient used by the research route."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = payload or MOCK_ML_REPORT
    mock_response.text = str(payload or {})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls, mock_client


def test_get_report_unauthenticated(client):
    """Requesting a report without login should return 401."""
    response = client.post("/api/v1/research/report", json={"ticker": "AAPL"})
    assert response.status_code == 401


def test_get_report_rejected_below_min_tier(auth_client):
    """A Foundation-tier (tier 1) user should be rejected with 403."""
    client_auth, _user_id = auth_client

    response = client_auth.post("/api/v1/research/report", json={"ticker": "AAPL"})
    assert response.status_code == 403


def test_get_report_success_for_growth_tier(db: Session, auth_client):
    """A Growth-tier (tier 2+) user should get the ml service's report back."""
    client_auth, user_id = auth_client

    subscription = db.query(Subscription).filter_by(user_id=user_id).first()
    subscription.tier_id = 2
    db.commit()

    mock_client_cls, mock_client = _mock_ml_client()
    with patch("app.api.routes.research.httpx.AsyncClient", mock_client_cls):
        response = client_auth.post("/api/v1/research/report", json={"ticker": "AAPL"})

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"

    # Real tier is forwarded to ml via header + body; never trust a client-supplied one.
    _, kwargs = mock_client.post.call_args
    assert kwargs["headers"]["x-tier-id"] == "2"
    assert kwargs["json"]["tier"] == 2


def test_get_report_propagates_ml_error(db: Session, auth_client):
    """A non-200 ml response should surface as the same status code."""
    client_auth, user_id = auth_client

    subscription = db.query(Subscription).filter_by(user_id=user_id).first()
    subscription.tier_id = 2
    db.commit()

    mock_client_cls, _mock_client = _mock_ml_client(
        status_code=404, payload={"detail": "No market data found for ticker 'ZZZZZ'."}
    )
    with patch("app.api.routes.research.httpx.AsyncClient", mock_client_cls):
        response = client_auth.post("/api/v1/research/report", json={"ticker": "ZZZZZ"})

    assert response.status_code == 404
