import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.subscriptions import (
    Subscription,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.tiers import Tier
from app.models.users import User

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


from app.schemas.stripe import CheckoutSessionRequest


class MockSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/create-checkout-session", response_model=MockSessionResponse)
def create_checkout_session(
    request: CheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mock endpoint to create a checkout session.
    It will bypass Stripe and directly transition to the success URL.
    """
    # Simply create a fake session id
    session_id = f"mock_session_{uuid.uuid4().hex}"

    # We can automatically upgrade them here, or let the success page trigger it.
    # We'll upgrade them here so when they land on success, it's done.
    tier = (
        db.query(Tier)
        .filter(
            (Tier.stripe_monthly_price_id == request.price_id)
            | (Tier.stripe_yearly_price_id == request.price_id)
        )
        .first()
    )

    if tier:
        # Update or create subscription locally
        subscription = db.query(Subscription).filter_by(user_id=current_user.id).first()
        if not subscription:
            subscription = Subscription(user_id=current_user.id)
            db.add(subscription)

        subscription.tier_id = tier.id
        subscription.status = SubscriptionStatus.active
        subscription.source = SubscriptionSource.free  # Mocked

        current_user.tier_id = tier.id
        db.commit()

    # Append the session_id so frontend knows it succeeded
    success_url = request.success_url.replace("{CHECKOUT_SESSION_ID}", session_id)

    return {"checkout_url": success_url, "session_id": session_id}
