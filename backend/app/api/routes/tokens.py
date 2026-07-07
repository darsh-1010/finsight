from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.users import User
from app.schemas.tokens import TokenTransactionList, TokenUsage
from app.services.token_service import TokenService

router = APIRouter(prefix="/api/v1/tokens", tags=["Tokens"])


@router.get("/usage", response_model=TokenUsage)
def get_token_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TokenService.get_usage(db, current_user)


@router.get("/transactions", response_model=TokenTransactionList)
def get_token_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = TokenService.get_transactions(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return {
        "items": transactions,
        "limit": limit,
        "offset": offset,
    }
