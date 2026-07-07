from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.entitlement_service import EntitlementService


def require_entitlement(entitlement_code: str):
    def dependency(
        db: Session = Depends(get_db),
        user=Depends(get_current_user),
    ):
        entitlements = EntitlementService.get_user_entitlements(db=db, user_id=user.id)

        if entitlement_code not in entitlements:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature not available for your current plan",
            )

        return True

    return dependency
