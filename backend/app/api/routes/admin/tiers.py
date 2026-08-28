from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_db, require_role
from app.models.tiers import Tier
from app.models.users import User
from app.schemas.tiers import TierResponse, TierUpdate

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
    _update_basic_fields(db_tier, update_data)

    db.commit()
    db.refresh(db_tier)
    return db_tier


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
