import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.signals import SignalType, SignalStatus
from app.models.insights import TrendType, InsightStatus

class InsightResponse(BaseModel):
    id: uuid.UUID
    summary: Optional[str]
    source: Optional[str]
    tier_required: int
    
    ticker: Optional[str]
    trend_type: Optional[TrendType]
    trend: Optional[str]
    price_change_pct: Optional[float]
    key_event: Optional[str]
    verification_status: Optional[str]
    citations: Optional[List[str]]
    alert_message: Optional[str]
    status: InsightStatus
    
    published_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class SignalResponse(BaseModel):
    id: int
    asset: str
    signal_type: SignalType
    explanation: Optional[str]
    tier_required: int
    status: SignalStatus
    approved: bool
    approved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
