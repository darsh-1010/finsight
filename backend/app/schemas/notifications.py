from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.notifications import AudienceType, NotificationPriority


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: Optional[str]
    notification_type: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    priority: NotificationPriority
    action_url: Optional[str]
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_read: bool
    audience_types: list[AudienceType]

    class Config:
        from_attributes = True


class NotificationReadResponse(BaseModel):
    id: int
    notification_id: int
    is_read: bool
    read_at: datetime
