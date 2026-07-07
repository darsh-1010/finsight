from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tiers import Tier
from app.models.tokens import (
    DailyTokenUsage,
    TierTokenConfig,
    TokenTransactions,
    UserTokenWallets,
)
from app.models.users import User


@dataclass
class TierTokenLimits:
    weekly_tokens: int
    daily_token_limit: int
    monthly_token_limit: int | None
    refill_frequency: str
    max_tokens_per_prompt: int


DEFAULT_TIER_TOKEN_LIMITS: dict[int, TierTokenLimits] = {
    1: TierTokenLimits(1000, 200, 4000, "weekly", 100),
    2: TierTokenLimits(5000, 1000, 20000, "weekly", 500),
    3: TierTokenLimits(10000, 2000, 40000, "weekly", 1000),
    4: TierTokenLimits(20000, 5000, 80000, "weekly", 2000),
}


class TokenService:
    @staticmethod
    def _get_tier_token_limits(db: Session, tier: Tier) -> TierTokenLimits:
        config = (
            db.query(TierTokenConfig).filter(TierTokenConfig.tier_id == tier.id).first()
        )
        if config:
            return TierTokenLimits(
                weekly_tokens=config.weekly_tokens,
                daily_token_limit=config.daily_token_limit,
                monthly_token_limit=config.monthly_token_limit,
                refill_frequency=config.refill_frequency,
                max_tokens_per_prompt=config.max_tokens_per_prompt,
            )
        return DEFAULT_TIER_TOKEN_LIMITS.get(
            tier.level,
            DEFAULT_TIER_TOKEN_LIMITS[1],
        )

    @staticmethod
    def _next_refill_at(now: datetime, refill_frequency: str) -> datetime:
        if refill_frequency == "monthly":
            return now + timedelta(days=30)
        return now + timedelta(days=7)

    @staticmethod
    def _record_transaction(
        db: Session,
        *,
        user_id: int,
        transaction_type: str,
        tokens: int,
        balance_before: int,
        balance_after: int,
        reference_type: str | None = None,
        reference_id: int | None = None,
        description: str | None = None,
        extra_metadata: dict | None = None,
    ) -> TokenTransactions:
        tx = TokenTransactions(
            user_id=user_id,
            transaction_type=transaction_type,
            tokens=tokens,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            extra_metadata=extra_metadata,
        )
        db.add(tx)
        return tx

    @staticmethod
    def get_or_create_wallet(db: Session, user: User) -> UserTokenWallets:
        wallet = (
            db.query(UserTokenWallets)
            .filter(UserTokenWallets.user_id == user.id)
            .first()
        )
        if wallet:
            return wallet

        tier = user.subscription.tier if user.subscription else None
        if not tier:
            tier = db.query(Tier).filter(Tier.level == 1).first()
            if not tier:
                raise HTTPException(
                    status_code=500, detail="Default tier not configured"
                )

        return TokenService.create_wallet_for_user(db, user, tier)

    @staticmethod
    def create_wallet_for_user(
        db: Session,
        user: User,
        tier: Tier,
        *,
        transaction_type: str = "signup_bonus",
    ) -> UserTokenWallets:
        existing = (
            db.query(UserTokenWallets)
            .filter(UserTokenWallets.user_id == user.id)
            .first()
        )
        if existing:
            return existing

        limits = TokenService._get_tier_token_limits(db, tier)
        now = datetime.utcnow()

        wallet = UserTokenWallets(
            user_id=user.id,
            available_tokens=limits.weekly_tokens,
            total_used_tokens=0,
            last_refill_at=now,
            next_refill_at=TokenService._next_refill_at(now, limits.refill_frequency),
        )
        db.add(wallet)
        db.flush()

        TokenService._record_transaction(
            db,
            user_id=user.id,
            transaction_type=transaction_type,
            tokens=limits.weekly_tokens,
            balance_before=0,
            balance_after=limits.weekly_tokens,
            reference_type="subscription",
            reference_id=tier.id,
            description=f"Initial token allocation for {tier.name}",
            extra_metadata={"tier_level": tier.level},
        )
        return wallet

    @staticmethod
    def refill_wallet_for_tier(
        db: Session,
        user: User,
        tier: Tier,
        *,
        transaction_type: str = "refill",
        description: str | None = None,
        extra_metadata: dict | None = None,
        now: datetime | None = None,
    ) -> UserTokenWallets:
        wallet = TokenService.get_or_create_wallet(db, user)
        limits = TokenService._get_tier_token_limits(db, tier)
        now = now or datetime.utcnow()
        tx_metadata = {"tier_level": tier.level}
        if extra_metadata:
            tx_metadata.update(extra_metadata)

        balance_before = wallet.available_tokens
        wallet.available_tokens = limits.weekly_tokens
        wallet.last_refill_at = now
        wallet.next_refill_at = TokenService._next_refill_at(
            now, limits.refill_frequency
        )

        TokenService._record_transaction(
            db,
            user_id=user.id,
            transaction_type=transaction_type,
            tokens=limits.weekly_tokens - balance_before,
            balance_before=balance_before,
            balance_after=wallet.available_tokens,
            reference_type="subscription",
            reference_id=tier.id,
            description=description or f"Token refill for {tier.name}",
            extra_metadata=tx_metadata,
        )
        return wallet

    @staticmethod
    def deduct_tokens_for_chat(
        db: Session,
        user: User,
        tokens_used: int,
        *,
        chat_message_id: int | None = None,
        description: str | None = None,
        extra_metadata: dict | None = None,
    ) -> UserTokenWallets:
        if tokens_used <= 0:
            return TokenService.get_or_create_wallet(db, user)

        wallet = TokenService.get_or_create_wallet(db, user)
        daily_usage = TokenService.get_daily_usage(db, user.id)

        balance_before = wallet.available_tokens
        wallet.available_tokens = balance_before - tokens_used
        wallet.total_used_tokens += tokens_used
        daily_usage.tokens_used += tokens_used

        TokenService._record_transaction(
            db,
            user_id=user.id,
            transaction_type="deduction",
            tokens=-tokens_used,
            balance_before=balance_before,
            balance_after=wallet.available_tokens,
            reference_type="chat_message",
            reference_id=chat_message_id,
            description=description or "Chat token usage",
            extra_metadata=extra_metadata,
        )
        return wallet

    @staticmethod
    def get_daily_usage(
        db: Session, user_id: int, usage_date: date | None = None
    ) -> DailyTokenUsage:
        usage_date = usage_date or date.today()
        usage = (
            db.query(DailyTokenUsage)
            .filter(
                DailyTokenUsage.user_id == user_id,
                DailyTokenUsage.usage_date == usage_date,
            )
            .first()
        )
        if usage:
            return usage

        usage = DailyTokenUsage(
            user_id=user_id,
            usage_date=usage_date,
            tokens_used=0,
        )
        db.add(usage)
        db.flush()
        return usage

    @staticmethod
    def get_usage(db: Session, user: User) -> dict:
        if not user.subscription or not user.subscription.tier:
            raise HTTPException(
                status_code=400, detail="User has no active subscription tier"
            )

        tier = user.subscription.tier
        wallet = TokenService.get_or_create_wallet(db, user)
        limits = TokenService._get_tier_token_limits(db, tier)
        daily_usage = TokenService.get_daily_usage(db, user.id)

        return {
            "user_id": user.id,
            "tier_level": tier.level,
            "tier_name": tier.name,
            "available_tokens": wallet.available_tokens,
            "total_used_tokens": wallet.total_used_tokens,
            "daily_tokens_used": daily_usage.tokens_used,
            "daily_token_limit": limits.daily_token_limit,
            "weekly_tokens": limits.weekly_tokens,
            "monthly_token_limit": limits.monthly_token_limit,
            "max_tokens_per_prompt": limits.max_tokens_per_prompt,
            "refill_frequency": limits.refill_frequency,
            "last_refill_at": wallet.last_refill_at,
            "next_refill_at": wallet.next_refill_at,
            "usage_date": daily_usage.usage_date,
        }

    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TokenTransactions]:
        return (
            db.query(TokenTransactions)
            .filter(TokenTransactions.user_id == user_id)
            .order_by(TokenTransactions.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
