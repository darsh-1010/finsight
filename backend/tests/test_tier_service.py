import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.users import User, Role, UserRole
from app.models.tiers import Tier
from app.models.subscriptions import Subscription, SubscriptionChange, SubscriptionStatus, ChangeType, ChangeSource
from app.services.tier_service import TierService

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Setup initial data: Role and Tiers
    role = Role(role=UserRole.USER)
    db.add(role)

    tier1 = Tier(name="Foundation", level=1, description="Free tier", price_amount=0)
    tier2 = Tier(name="Pro", level=2, description="Paid tier", price_amount=99900)
    db.add_all([tier1, tier2])

    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_assign_default_subscription(db):
    user = User(email="test@example.com", password_hash="hash")
    db.add(user)
    db.commit()

    TierService.assign_default_subscription(db, user)

    # Refresh user
    db.refresh(user)

    assert user.subscription is not None
    assert user.subscription.tier.level == 1
    assert user.subscription.status == SubscriptionStatus.ACTIVE

    # Check change log
    change = db.query(SubscriptionChange).filter(SubscriptionChange.user_id == user.id).first()
    assert change is not None
    assert change.change_type == ChangeType.SIGNUP
    assert change.new_tier_id == user.subscription.tier_id

def test_change_tier_upgrade(db):
    user = User(email="test@example.com", password_hash="hash")
    db.add(user)
    db.commit()

    # Start with tier 1
    TierService.assign_default_subscription(db, user)

    # Upgrade to tier 2
    TierService.change_tier(
        db,
        user,
        new_tier_level=2,
        change_type=ChangeType.UPGRADE,
        source=ChangeSource.USER
    )

    db.refresh(user)
    assert user.subscription.tier.level == 2

    # Check change log
    changes = db.query(SubscriptionChange).filter(SubscriptionChange.user_id == user.id).order_by(SubscriptionChange.id.desc()).all()
    assert len(changes) == 2
    assert changes[0].change_type == ChangeType.UPGRADE
    assert changes[0].previous_tier_id is not None

    # Check previous change is closed
    assert changes[1].effective_to is not None

def test_invalid_tier_level(db):
    user = User(email="test@example.com", password_hash="hash")
    db.add(user)
    db.commit()

    with pytest.raises(Exception): # FastAPI's HTTPException might be caught or raised directly
        TierService.change_tier(
            db,
            user,
            new_tier_level=999,
            change_type=ChangeType.UPGRADE,
            source=ChangeSource.USER
        )
