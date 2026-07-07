from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.compliance import ComplianceGroup
from app.models.insights import Insight, InsightStatus
from app.models.signals import Signal
from app.models.users import User
from app.schemas.compliance import ComplianceGroupResponse
from app.schemas.content import InsightResponse, SignalResponse

router = APIRouter(prefix="/api/v1/content", tags=["Content"])


@router.get("/insights", response_model=List[InsightResponse])
async def get_approved_insights(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # keep auth, avoid unused warning
):
    """
    Fetch all approved insights. Accessible by all authenticated users.
    """
    return (
        db.query(Insight)
        .filter(Insight.status == InsightStatus.APPROVED)
        .order_by(Insight.published_at.desc())
        .all()
    )


@router.get("/signals", response_model=List[SignalResponse])
async def get_approved_signals(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # keep auth, avoid unused warning
):
    """
    Fetch all approved signals. Accessible by all authenticated users.
    """
    return db.query(Signal).filter(Signal.approved.is_(True)).all()


# Public APIs

@router.get("/compliance/groups/{key}", response_model=ComplianceGroupResponse)
async def get_compliance_group(
    key: str,
    db: Session = Depends(get_db),
):
    group = (
        db.query(ComplianceGroup)
        .filter(ComplianceGroup.key == key)
        .first()
    )

    if not group:
        raise HTTPException(
            status_code=404,
            detail="Compliance group not found",
        )

    return group
