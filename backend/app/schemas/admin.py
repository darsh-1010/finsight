from pydantic import BaseModel

from app.models.insights import InsightStatus


class ApprovalRequest(BaseModel):
    entity_id: int | str
    approved: bool


class InsightStatusUpdateRequest(BaseModel):
    entity_id: int | str
    status: InsightStatus
    review_notes: str | None = None
