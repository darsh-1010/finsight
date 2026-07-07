import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.insights import InsightStatus, TrendType
from app.models.signals import SignalStatus, SignalType


class InsightResponse(BaseModel):
    id: uuid.UUID
    summary: str | None
    source: str | None
    tier_required: int

    ticker: str | None
    trend_type: TrendType | None
    trend: str | None
    price_change_pct: float | None
    key_event: str | None
    verification_status: str | None
    citations: list[str] | None
    alert_message: str | None
    status: InsightStatus

    published_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: int
    asset: str
    signal_type: SignalType
    explanation: str | None
    tier_required: int
    status: SignalStatus
    approved: bool
    approved_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
