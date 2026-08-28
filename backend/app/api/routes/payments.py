from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.subscriptions import ChangeSource, ChangeType
from app.models.users import User
from app.services.tier_service import TierService

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


class TierSelectRequest(BaseModel):
    tier_level: int


class TierSelectResponse(BaseModel):
    status: str
    tier_level: int


@router.post("/select-tier", response_model=TierSelectResponse)
def select_tier(
    request: TierSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Switch the current user to any tier, free of charge and immediately.
    """
    current_level = 1
    if current_user.subscription and current_user.subscription.tier:
        current_level = current_user.subscription.tier.level

    change_type = (
        ChangeType.UPGRADE
        if request.tier_level >= current_level
        else ChangeType.DOWNGRADE
    )

    TierService.change_tier(
        db,
        current_user,
        request.tier_level,
        change_type=change_type,
        source=ChangeSource.USER,
    )

    return {"status": "success", "tier_level": request.tier_level}
