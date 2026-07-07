from datetime import datetime

from pydantic import BaseModel

from app.models.notifications import AudienceType, NotificationPriority


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str | None
    notification_type: str
    entity_type: str | None
    entity_id: str | None
    priority: NotificationPriority
    action_url: str | None
    created_by: str
    created_at: datetime
    expires_at: datetime | None
    is_read: bool
    audience_types: list[AudienceType]

    class Config:
        from_attributes = True


class NotificationReadResponse(BaseModel):
    id: int
    notification_id: int
    is_read: bool
    read_at: datetime
