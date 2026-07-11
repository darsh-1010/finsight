import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.users import User
from app.models.subscriptions import Subscription, SubscriptionStatus

def test_create_checkout_session_unauthenticated(client: TestClient):
    """Creating a checkout session without login should return 401."""
    response = client.post(
        "/api/v1/payments/create-checkout-session",
        json={
            "price_id": "mock_price_2",
            "success_url": "http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost/cancel"
        }
    )
    assert response.status_code == 401

def test_create_checkout_session_success_upgrades_tier(db: Session, auth_client):
    """Creating a checkout session with valid mock price ID upgrades user's tier and subscription."""
    client_auth, user_id = auth_client

    # Verify user's initial state is basic (tier level 1 or default)
    user = db.query(User).filter(User.id == user_id).first()
    assert user.tier_id == 1 or user.tier_id is None

    # Call checkout session for tier level 2 (Growth)
    response = client_auth.post(
        "/api/v1/payments/create-checkout-session",
        json={
            "price_id": "mock_price_2",
            "success_url": "http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost/cancel"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data
    assert "session_id" in data
    assert "mock_session_" in data["session_id"]
    assert data["checkout_url"] == f"http://localhost/success?session_id={data['session_id']}"

    # Refresh DB session & check that user tier and subscription are active
    db.expire_all()
    user = db.query(User).filter(User.id == user_id).first()
    assert user.tier_id == 2

    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    assert sub is not None
    assert sub.tier_id == 2
    assert sub.status == SubscriptionStatus.ACTIVE

def test_create_checkout_session_invalid_price_does_not_upgrade(db: Session, auth_client):
    """Creating a checkout session with an invalid price ID returns a mock URL but doesn't change the tier."""
    client_auth, user_id = auth_client

    # Verify user's initial state
    user = db.query(User).filter(User.id == user_id).first()
    initial_tier_id = user.tier_id

    response = client_auth.post(
        "/api/v1/payments/create-checkout-session",
        json={
            "price_id": "invalid_price_id_here",
            "success_url": "http://localhost/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost/cancel"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data

    db.expire_all()
    user = db.query(User).filter(User.id == user_id).first()
    assert user.tier_id == initial_tier_id
