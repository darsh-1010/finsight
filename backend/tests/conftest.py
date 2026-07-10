"""
Shared pytest configuration and fixtures for the backend test suite.

Uses in-memory SQLite (StaticPool) to avoid any PostgreSQL dependency.
External services (SES, Stripe, boto3, cron) are globally mocked so
tests never make real network calls.
"""

# ── stdlib / third-party first to avoid import-order issues ──────────────────
import os
import sys
from unittest.mock import MagicMock, patch

# Force SQLite DATABASE_URL before any app code is imported.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
# Pydantic's assemble_cors_origins validator accepts JSON array format
os.environ.setdefault("BACKEND_CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("COOKIE_SECURE", "false")

# ── Patch SQLAlchemy ARRAY type for SQLite compatibility ─────────────────────
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.types import ARRAY  # noqa: E402


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(element, compiler, **kw):
    """SQLite does not support ARRAY; treat as TEXT."""
    return "TEXT"


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# ── App imports (after env vars are set) ─────────────────────────────────────
from app.api.deps import get_db as get_db_deps  # noqa: E402
from app.core.database import get_db as get_db_core  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.tiers import Tier  # noqa: E402
from app.models.users import Role, UserRole  # noqa: E402

# Disable secure cookies so TestClient (http) can handle them
settings.COOKIE_SECURE = False

# ── Shared in-memory engine ──────────────────────────────────────────────────
SQLITE_URL = "sqlite://"
_engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


# ── Session-scoped DB setup ──────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once per test session, then drop them."""
    # Import every model so SQLAlchemy registers metadata
    import app.models  # noqa: F401 — triggers all model registrations

    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def _seed_roles_and_tiers(_create_tables):
    """
    Seed foundational Roles and Tiers once per session.
    Individual tests that mutate data must use the function-scoped `db` fixture.
    """
    db = TestingSessionLocal()
    try:
        # Roles
        if not db.query(Role).filter(Role.id == 1).first():
            db.add(Role(id=1, role=UserRole.USER))
        if not db.query(Role).filter(Role.id == 2).first():
            db.add(Role(id=2, role=UserRole.ADMIN))

        # Tiers (levels 1–4)
        tier_definitions = [
            {"id": 1, "name": "Foundation", "level": 1, "description": "Free tier", "price_amount": 0},
            {"id": 2, "name": "Growth", "level": 2, "description": "Growth tier", "price_amount": 999},
            {"id": 3, "name": "Professional", "level": 3, "description": "Pro tier", "price_amount": 1999},
            {"id": 4, "name": "Elite", "level": 4, "description": "Elite tier", "price_amount": 2999},
        ]
        for td in tier_definitions:
            if not db.query(Tier).filter(Tier.id == td["id"]).first():
                db.add(Tier(**td))
        db.commit()
    finally:
        db.close()


# ── Function-scoped DB fixture ───────────────────────────────────────────────
@pytest.fixture
def db():
    """
    Provide a transactional database session that rolls back after each test,
    ensuring full test isolation without table recreation overhead.
    """
    connection = _engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── Client fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def client(db):
    """Unauthenticated TestClient backed by the test DB."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_deps] = _override_get_db
    app.dependency_overrides[get_db_core] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register_user(test_client: TestClient, email: str = "testuser@example.com", password: str = "Password123!") -> dict:
    """Helper: sign up + log in, returning the authenticated client and user info."""
    signup_resp = test_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "role_id": 1},
    )
    assert signup_resp.status_code == 200, f"Signup failed: {signup_resp.text}"
    login_resp = test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return signup_resp.json()


@pytest.fixture
def auth_client(db):
    """
    TestClient that is already authenticated as a regular user.
    Returns (client, user_id) tuple.
    """

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_deps] = _override_get_db
    app.dependency_overrides[get_db_core] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        user_data = _register_user(test_client)
        yield test_client, user_data.get("user_id")
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(db):
    """TestClient authenticated as an admin user."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_deps] = _override_get_db
    app.dependency_overrides[get_db_core] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        user_data = _register_user(test_client, email="admin@example.com", password="AdminPass123!")
        yield test_client, user_data.get("user_id")
    app.dependency_overrides.clear()


# ── Global external-service mocks ─────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _mock_ses_service():
    """Prevent any real SES / email calls during tests."""
    with patch("app.services.ses_service.ses_service.send_verification_email", return_value=None), \
         patch("app.services.ses_service.ses_service.send_password_reset_email", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _mock_stripe():
    """Prevent real Stripe API calls during tests."""
    mock_customer = MagicMock()
    mock_customer.id = "cus_test_placeholder"
    with patch("app.services.stripe_service.StripeService.get_or_create_customer", return_value=mock_customer):
        yield


@pytest.fixture(autouse=True)
def _mock_cron():
    """Prevent the cron service from starting during test startup."""
    with patch("app.services.cron.cron_service.start", return_value=None), \
         patch("app.services.cron.cron_service.stop", return_value=None):
        yield
