from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatMessageBase(BaseModel):
    content: str
    role: str  # 'user' or 'bot' align with frontend
    non_substantive: bool = False


class ChatMessageCreate(ChatMessageBase):
    model: str | None = "standard"
    attachment_ids: list[UUID] | None = []


class AttachmentRead(BaseModel):
    id: UUID
    file_name: str
    file_type: str | None
    file_size: int | None
    storage_url: str | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatMessage(ChatMessageBase):
    id: int
    session_id: int
    created_at: datetime
    suggested_follow_ups: list[str] | None = []
    attachments: list[AttachmentRead] = []
    model_config = ConfigDict(from_attributes=True)


class MLChatMessage(BaseModel):
    created_at: datetime
    content: str
    role: str
    model_config = ConfigDict(from_attributes=True)


class ChatSessionBase(BaseModel):
    title: str | None = None
    model: str = "standard"


class ChatSessionCreate(ChatSessionBase):
    first_message: str | None = None


class ChatSession(ChatSessionBase):
    id: int
    user_id: int
    session_id: UUID
    started_at: datetime
    messages: list[ChatMessage] = []
    model_config = ConfigDict(from_attributes=True)


class ChatUsage(BaseModel):
    user_id: int
    date: date
    messages_used: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Attachment Upload ---------- #


class AttachmentResult(BaseModel):
    """Per-file upload result."""

    id: UUID | None = None
    filename: str
    attached: bool
    message: str
    ml_response: dict[str, Any] | None = None


class AttachmentUploadResponse(BaseModel):
    """Overall response for the attachment upload endpoint."""

    session_id: str
    results: list[AttachmentResult]
