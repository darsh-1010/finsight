from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TierTokenConfig(Base):
    __tablename__ = "tier_token_configs"

    id = Column(Integer, primary_key=True, index=True)

    # FK to tiers table
    tier_id = Column(
        BigInteger,
        ForeignKey("tiers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Weekly token allocation
    weekly_tokens = Column(Integer, nullable=False, default=0)

    # Daily usage cap
    daily_token_limit = Column(Integer, nullable=False, default=0)

    # Optional future monthly cap
    monthly_token_limit = Column(Integer, nullable=True)

    # weekly / monthly
    refill_frequency = Column(String(20), nullable=False, default="weekly")

    # Max token usage allowed in one request
    max_tokens_per_prompt = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tier = relationship("Tier", back_populates="token_config")


class UserTokenWallets(Base):
    __tablename__ = "user_token_wallets"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Current usable balance
    available_tokens = Column(Integer, nullable=False, default=0)

    # Lifetime usage tracking
    total_used_tokens = Column(BigInteger, nullable=False, default=0)

    # Refill tracking
    last_refill_at = Column(DateTime(timezone=True), nullable=True)

    next_refill_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="token_wallet")


class DailyTokenUsage(Base):
    __tablename__ = "daily_token_usage"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Current date for usage tracking
    usage_date = Column(Date, nullable=False, index=True)

    # Tokens consumed today
    tokens_used = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "usage_date",
            name="uq_daily_token_usage_user_date",
        ),
    )

    # Relationships
    user = relationship("User", back_populates="daily_token_usage")


class TokenTransactions(Base):
    __tablename__ = "token_transactions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # refill / deduction / upgrade_bonus / admin_adjustment
    transaction_type = Column(String(50), nullable=False, index=True)

    # +100 / -1 etc
    tokens = Column(Integer, nullable=False)

    # Balance snapshot
    balance_before = Column(Integer, nullable=False)

    balance_after = Column(Integer, nullable=False)

    # chat_message / subscription / admin
    reference_type = Column(String(50), nullable=True)

    # ID of related entity
    reference_id = Column(BigInteger, nullable=True)

    # Extra transaction details (DB column: metadata)
    extra_metadata = Column("metadata", JSON, nullable=True)

    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="token_transactions")
