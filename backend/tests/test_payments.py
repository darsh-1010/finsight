from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.subscriptions import Subscription, SubscriptionStatus


def test_select_tier_unauthenticated(client: TestClient):
    """Selecting a tier without login should return 401."""
    response = client.post(
        "/api/v1/payments/select-tier",
        json={"tier_level": 2},
    )
    assert response.status_code == 401


def test_select_tier_upgrades_immediately(db: Session, auth_client):
    """Selecting a higher tier is free and applies immediately."""
    client_auth, user_id = auth_client

    response = client_auth.post(
        "/api/v1/payments/select-tier",
        json={"tier_level": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "success", "tier_level": 2}

    db.expire_all()
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    assert sub is not None
    assert sub.tier_id == 2
    assert sub.status == SubscriptionStatus.ACTIVE


def test_select_tier_invalid_level_rejected(auth_client):
    """Selecting a tier level that doesn't exist returns 400."""
    client_auth, _user_id = auth_client

    response = client_auth.post(
        "/api/v1/payments/select-tier",
        json={"tier_level": 999},
    )
    assert response.status_code == 400
