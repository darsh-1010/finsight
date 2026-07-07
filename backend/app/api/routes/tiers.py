from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tiers import Tier
from app.schemas.tiers import TierResponse

router = APIRouter(prefix="/api/v1/tiers", tags=["Tiers"])


@router.get("", response_model=list[TierResponse])
def get_all_tiers(db: Session = Depends(get_db)):
    """
    Fetch all pricing tiers for frontend pricing cards.
    """
    tiers = db.query(Tier).order_by(Tier.level.asc()).all()

    return tiers
