from sqlalchemy.orm import Session

from app.models.subscriptions import Subscription
from app.models.tiers import Entitlements, Tier, TierEntitlement


class EntitlementService:
    @staticmethod
    def get_user_entitlements(db: Session, user_id: int) -> set[str]:
        subscription = (
            db.query(Subscription)
            .filter(Subscription.user_id == user_id, Subscription.status == "active")
            .first()
        )

        if not subscription:
            return set()

        # Get the tier level of the user's active subscription
        user_tier_level = subscription.tier.level

        # Query all entitlements that are included in the user's tier or lower tiers
        # Note: Usually entitlements are cumulative, so we check Tier.level <= user_tier_level
        rows = (
            db.query(Entitlements)
            .join(TierEntitlement)
            .join(Tier)
            .filter(Tier.level <= user_tier_level)
            .all()
        )

        return {ent.code for ent in rows}
