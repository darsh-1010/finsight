from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.subscriptions import Subscription, SubscriptionStatus
from app.models.tiers import Tier
from app.models.tokens import DailyTokenUsage, TokenTransactions, UserTokenWallets
from app.models.users import User
from app.services.chat_service import ChatService
from app.services.token_service import TokenService

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_deduct_tokens_for_chat_updates_wallet_daily_usage_and_transaction():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        user = User(email="token-deduction@example.com", password_hash="hash")
        tier = Tier(name="Foundation", level=1, description="Free tier", price_amount=0)
        db.add_all([user, tier])
        db.flush()

        db.add(
            Subscription(
                user_id=user.id,
                tier_id=tier.id,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        wallet = UserTokenWallets(
            user_id=user.id,
            available_tokens=1000,
            total_used_tokens=25,
        )
        db.add(wallet)
        db.commit()

        TokenService.deduct_tokens_for_chat(
            db,
            user,
            123,
            chat_message_id=456,
            extra_metadata={"source": "chat_stream"},
        )
        db.commit()
        db.refresh(wallet)

        daily_usage = db.query(DailyTokenUsage).filter_by(user_id=user.id).one()
        transaction = db.query(TokenTransactions).filter_by(user_id=user.id).one()

        assert wallet.available_tokens == 877
        assert wallet.total_used_tokens == 148
        assert daily_usage.tokens_used == 123
        assert transaction.transaction_type == "deduction"
        assert transaction.tokens == -123
        assert transaction.balance_before == 1000
        assert transaction.balance_after == 877
        assert transaction.reference_type == "chat_message"
        assert transaction.reference_id == 456
        assert transaction.extra_metadata["source"] == "chat_stream"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_extract_total_tokens_from_stream_payload_shapes():
    assert ChatService._extract_total_tokens({"total_tokens": 12}) == 12
    assert ChatService._extract_total_tokens({"data": {"total_tokens": "34"}}) == 34
    assert (
        ChatService._extract_total_tokens({"data": {"usage": {"total_tokens": 56}}})
        == 56
    )
    assert ChatService._extract_total_tokens({"usage": {"total_tokens": 78}}) == 78
    assert ChatService._extract_total_tokens({"data": {"content": "hello"}}) is None
