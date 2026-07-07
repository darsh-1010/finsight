import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.subscriptions import Subscription, SubscriptionStatus
from app.models.tiers import Entitlements, Tier, TierEntitlement
from app.models.users import Role, User, UserRole
from app.services.entitlement_service import EntitlementService

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

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Setup initial data: Roles and Tiers
    user_role = Role(id=1, role=UserRole.USER)
    db.add(user_role)

    tier1 = Tier(
        id=1, name="Foundation", level=1, description="Free tier", price_amount=0
    )
    tier2 = Tier(id=2, name="Pro", level=2, description="Paid tier", price_amount=99900)
    db.add_all([tier1, tier2])

    ent1 = Entitlements(id=1, code="basic_feature", description="Basic feature")
    ent2 = Entitlements(id=2, code="pro_feature", description="Pro feature")
    db.add_all([ent1, ent2])

    # Tier 1 has ent 1
    db.add(TierEntitlement(tier_id=1, entitlement_id=1))
    # Tier 2 has ent 1 and 2
    db.add(TierEntitlement(tier_id=2, entitlement_id=1))
    db.add(TierEntitlement(tier_id=2, entitlement_id=2))

    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_get_user_entitlements_basic(db):
    user = User(email="test@example.com", password_hash="hash", role_id=1)
    db.add(user)
    db.commit()

    sub = Subscription(user_id=user.id, tier_id=1, status=SubscriptionStatus.ACTIVE)
    db.add(sub)
    db.commit()

    entitlements = EntitlementService.get_user_entitlements(db, user.id)
    assert "basic_feature" in entitlements
    assert "pro_feature" not in entitlements


def test_get_user_entitlements_pro(db):
    user = User(email="pro@example.com", password_hash="hash", role_id=1)
    db.add(user)
    db.commit()

    sub = Subscription(user_id=user.id, tier_id=2, status=SubscriptionStatus.ACTIVE)
    db.add(sub)
    db.commit()

    entitlements = EntitlementService.get_user_entitlements(db, user.id)
    assert "basic_feature" in entitlements
    assert "pro_feature" in entitlements


def test_get_user_entitlements_no_sub(db):
    user = User(email="no@example.com", password_hash="hash", role_id=1)
    db.add(user)
    db.commit()

    entitlements = EntitlementService.get_user_entitlements(db, user.id)
    assert len(entitlements) == 0
