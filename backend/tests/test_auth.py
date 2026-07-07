import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.subscriptions import Subscription, SubscriptionChange
from app.models.users import User, Role, UserRole, UserSession, UserProfile
from app.models.tiers import Tier, Entitlements, TierEntitlement
from app.services.tier_service import TierService
from app.main import app
from fastapi.testclient import TestClient
from app.api.deps import get_db
from sqlalchemy.pool import StaticPool
from app.core.config import settings

settings.COOKIE_SECURE = False

# Use in-memory SQLite for testing with StaticPool to share connection
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    # Force registration by importing all models
    from app.models.users import User, Role, UserSession, UserProfile
    from app.models.tiers import Tier, Entitlements, TierEntitlement
    from app.models.subscriptions import Subscription, SubscriptionChange

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Setup initial data: Roles and Tiers
    user_role = Role(id=1, role=UserRole.USER)
    admin_role = Role(id=2, role=UserRole.ADMIN)
    db.add_all([user_role, admin_role])

    tier1 = Tier(id=1, name="Foundation", level=1, description="Free tier", price_amount=0)
    db.add(tier1)

    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_signup_success(client, db):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123", "role_id": 1}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User created successfully"
    assert "user_id" in data

    user = db.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    assert user.subscription is not None
    assert user.subscription.tier_id == 1

def test_login_success(client, db):
    # Create user first
    client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123", "role_id": 1}
    )

    # Try login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies

def test_me_endpoint(client, db):
    # Signup and login
    client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123", "role_id": 1}
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )

    response = client.get("/api/v1/auth/me")
    if response.status_code != 200:
        print(f"DEBUG: /me failed with {response.status_code}: {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"

def test_logout(client, db):
    # Signup and login
    client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123", "role_id": 1}
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )

    response = client.get("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"
    assert "access_token" not in client.cookies
    assert "refresh_token" not in client.cookies
