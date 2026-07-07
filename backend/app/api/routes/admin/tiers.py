from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_db, require_role
from app.models.tiers import Tier
from app.models.users import User
from app.schemas.tiers import TierUpdate, TierResponse
from app.services.stripe_service import StripeService, stripe


router = APIRouter(prefix="/tiers", tags=["Admin Tiers"])


@router.put("/{tier_id}", response_model=TierResponse)
async def update_tier(
    tier_id: int,
    tier_update: TierUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    db_tier = db.query(Tier).filter(Tier.id == tier_id).first()
    if not db_tier:
        raise HTTPException(status_code=404, detail="Tier not found")

    update_data = tier_update.dict(exclude_unset=True)

    _update_product_details(db_tier, update_data)
    _update_monthly_price(db_tier, update_data)
    _update_yearly_price(db_tier, update_data)
    _update_basic_fields(db_tier, update_data)

    db.commit()
    db.refresh(db_tier)
    return db_tier


def _update_product_details(db_tier: Tier, update_data: dict) -> None:
    if not db_tier.stripe_product_id:
        return

    if "name" not in update_data and "description" not in update_data:
        return

    try:
        stripe.Product.modify(
            db_tier.stripe_product_id,
            name=update_data.get("name", db_tier.name),
            description=update_data.get("description", db_tier.description),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe product update failed: {str(exc)}",
        ) from exc


def _update_monthly_price(db_tier: Tier, update_data: dict) -> None:
    if "price_amount" not in update_data:
        return

    new_price = update_data["price_amount"]
    if new_price == db_tier.price_amount or not db_tier.stripe_product_id:
        return

    StripeService.archive_price(db_tier.stripe_price_id)
    new_price_id = StripeService.create_price(
        db_tier.stripe_product_id,
        new_price,
        "month",
    )
    db_tier.stripe_price_id = new_price_id


def _update_yearly_price(db_tier: Tier, update_data: dict) -> None:
    if "price_amount_yearly" not in update_data:
        return

    new_yearly_price = update_data["price_amount_yearly"]
    if (
        new_yearly_price == db_tier.price_amount_yearly
        or not db_tier.stripe_product_id
    ):
        return

    if db_tier.stripe_yearly_price_id:
        StripeService.archive_price(db_tier.stripe_yearly_price_id)

    if new_yearly_price and new_yearly_price > 0:
        new_price_id = StripeService.create_price(
            db_tier.stripe_product_id,
            new_yearly_price,
            "year",
        )
        db_tier.stripe_yearly_price_id = new_price_id
    else:
        db_tier.stripe_yearly_price_id = None


def _update_basic_fields(db_tier: Tier, update_data: dict) -> None:
    for key, value in update_data.items():
        if key != "highlights":
            setattr(db_tier, key, value)
            continue

        if not value:
            continue

        current_highlights = db_tier.highlights or []
        if not isinstance(current_highlights, list):
            current_highlights = []

        for item in value:
            if item not in current_highlights:
                current_highlights.append(item)

        db_tier.highlights = list(current_highlights)
        flag_modified(db_tier, "highlights")
