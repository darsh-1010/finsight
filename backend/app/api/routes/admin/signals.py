from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.signals import Signal
from app.models.users import User
from app.schemas.admin import ApprovalRequest

router = APIRouter(prefix="/signals", tags=["Admin Signals"])


@router.post("/approval")
async def update_signal_approval(
    request: ApprovalRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """
    Approve or unapprove a signal.
    Path: /api/v1/admin/signals/approval
    """
    item = db.query(Signal).filter(Signal.id == request.entity_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Signal not found")

    item.approved = request.approved
    item.approved_at = datetime.utcnow() if request.approved else None
    db.commit()

    status = "approved" if request.approved else "unapproved"
    return {"message": f"Signal {status} successfully"}
