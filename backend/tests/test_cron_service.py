from datetime import datetime, timedelta

from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.subscriptions import Subscription, SubscriptionStatus
from app.models.tiers import Tier
from app.models.tokens import TierTokenConfig, TokenTransactions, UserTokenWallets
from app.models.users import User
from app.services.cron_service import refill_due_token_wallets


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def test_refill_due_token_wallets_resets_balance_and_records_transaction():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        now = datetime.utcnow()

        user = User(email="cron@example.com", password_hash="hash")
        tier = Tier(name="Pro", level=2, description="Paid tier", price_amount=99900)
        db.add_all([user, tier])
        db.flush()

        db.add(
            TierTokenConfig(
                tier_id=tier.id,
                weekly_tokens=5000,
                daily_token_limit=1000,
                refill_frequency="weekly",
                max_tokens_per_prompt=500,
            )
        )
        db.add(
            Subscription(
                user_id=user.id,
                tier_id=tier.id,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        wallet = UserTokenWallets(
            user_id=user.id,
            available_tokens=123,
            total_used_tokens=0,
            last_refill_at=now - timedelta(days=7),
            next_refill_at=now - timedelta(minutes=1),
        )
        db.add(wallet)
        db.commit()

        refilled_count = refill_due_token_wallets(db, now=now)
        db.commit()
        db.refresh(wallet)

        transaction = db.query(TokenTransactions).filter_by(user_id=user.id).one()

        assert refilled_count == 1
        assert wallet.available_tokens == 5000
        assert wallet.last_refill_at == now
        assert wallet.next_refill_at == now + timedelta(days=7)
        assert transaction.transaction_type == "refill"
        assert transaction.tokens == 4877
        assert transaction.balance_before == 123
        assert transaction.balance_after == 5000
        assert transaction.extra_metadata["source"] == "cron"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_refill_due_token_wallets_ignores_future_refills():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        now = datetime.utcnow()

        user = User(email="future-cron@example.com", password_hash="hash")
        tier = Tier(name="Foundation", level=1, description="Free tier", price_amount=0)
        db.add_all([user, tier])
        db.flush()

        db.add(
            TierTokenConfig(
                tier_id=tier.id,
                weekly_tokens=1000,
                daily_token_limit=200,
                refill_frequency="weekly",
                max_tokens_per_prompt=100,
            )
        )
        db.add(
            Subscription(
                user_id=user.id,
                tier_id=tier.id,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        wallet = UserTokenWallets(
            user_id=user.id,
            available_tokens=500,
            total_used_tokens=0,
            last_refill_at=now,
            next_refill_at=now + timedelta(minutes=1),
        )
        db.add(wallet)
        db.commit()

        refilled_count = refill_due_token_wallets(db, now=now)
        db.commit()
        db.refresh(wallet)

        assert refilled_count == 0
        assert wallet.available_tokens == 500
        assert db.query(TokenTransactions).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
