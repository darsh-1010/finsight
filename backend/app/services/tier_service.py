from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.subscriptions import Subscription,SubscriptionChange, SubscriptionStatus, ChangeType, ChangeSource
from app.models.tiers import Tier
from app.models.users import User
from app.services.token_service import TokenService


class TierService:
    """
    Single source of truth for tier & subscription changes
    """

    # Helpers

    @staticmethod
    def _get_tier_by_level(db:Session,level:int) -> Tier:
        tier = db.query(Tier).filter(Tier.level == level).first()
        if not tier:
            raise HTTPException(status_code=400, detail = "Invalid tier level")
        return tier

    @staticmethod
    def get_or_create_subscription(db: Session, user: User) -> Subscription:
        if user.subscription:
            return user.subscription

        subscription = Subscription(
            user_id=user.id,
            status=SubscriptionStatus.ACTIVE,
            source="free"
        )

        db.add(subscription)
        db.flush()
        return subscription

    @staticmethod
    def _close_active_change(db: Session, user_id: int):
        """
        Close the currently active SubscriptionChange (effective_to=Null)
        """
        active = (
            db.query(SubscriptionChange)
            .filter(
                SubscriptionChange.user_id == user_id,
                SubscriptionChange.effective_to.is_(None)
            ).first()
        )

        if active:
            active.effective_to = datetime.utcnow()
            db.add(active)

    # Signup Flows

    @staticmethod
    def assign_default_subscription(db: Session, user: User):
        tier = TierService._get_tier_by_level(db, 1)
        subscription = TierService.get_or_create_subscription(db, user)
        subscription.tier_id = tier.id
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.source = "free"
        subscription.started_at = datetime.utcnow()

        db.add(SubscriptionChange(
            user_id=user.id,
            previous_tier_id=None,
            new_tier_id=tier.id,
            change_type=ChangeType.SIGNUP,
            source=ChangeSource.SYSTEM,
            effective_from=datetime.utcnow(),
            effective_to=None
        ))

        db.commit()
        return subscription

    # Core mutation method

    @staticmethod
    def change_tier(
        db: Session,
        user: User,
        new_tier_level: int,
        *,
        change_type: ChangeType,
        source: ChangeSource,
        effective_from: datetime | None = None,
    ):
        """
        Handles upgrade, downgrade, expiry, admin override, renewal.
        """
        subscription = TierService.get_or_create_subscription(db, user)
        new_tier = TierService._get_tier_by_level(db, new_tier_level)

        now = effective_from or datetime.utcnow()
        previous_tier_id = subscription.tier_id

        # Close existing tier window
        TierService._close_active_change(db, user.id)

        # Update subscription
        subscription.tier_id = new_tier.id
        subscription.status = (
            SubscriptionStatus.ACTIVE
            if change_type != ChangeType.EXPIRE
            else SubscriptionStatus.EXPIRED
        )
        subscription.started_at = now

        # Insert new change row
        db.add(
            SubscriptionChange(
                user_id=user.id,
                previous_tier_id=previous_tier_id,
                new_tier_id=new_tier.id,
                change_type=change_type,
                source=source,
                effective_from=now,
                effective_to=None,
            )
        )

        tx_type = "upgrade_bonus" if change_type == ChangeType.UPGRADE else "refill"
        TokenService.refill_wallet_for_tier(
            db,
            user,
            new_tier,
            transaction_type=tx_type,
        )

        db.commit()

        return subscription
