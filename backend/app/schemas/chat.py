from datetime import datetime, date
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ChatMessageBase(BaseModel):
    content: str
    role: str  # 'user' or 'bot' align with frontend
    non_substantive: bool = False

class ChatMessageCreate(ChatMessageBase):
    model: Optional[str] = "standard"
    attachment_ids: Optional[List[UUID]] = []

class AttachmentRead(BaseModel):
    id: UUID
    file_name: str
    file_type: Optional[str]
    file_size: Optional[int]
    storage_url: Optional[str]
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChatMessage(ChatMessageBase):
    id: int
    session_id: int
    created_at: datetime
    suggested_follow_ups: Optional[List[str]] = []
    attachments: List[AttachmentRead] = []
    model_config = ConfigDict(from_attributes=True)

class MLChatMessage(BaseModel):
    created_at: datetime
    content: str
    role: str
    model_config = ConfigDict(from_attributes=True)

class ChatSessionBase(BaseModel):
    title: Optional[str] = None
    model: str = "standard"

class ChatSessionCreate(ChatSessionBase):
    first_message: Optional[str] = None

class ChatSession(ChatSessionBase):
    id: int
    user_id: int
    session_id: UUID
    started_at: datetime
    messages: List[ChatMessage] = []
    model_config = ConfigDict(from_attributes=True)

class ChatUsage(BaseModel):
    user_id: int
    date: date
    messages_used: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Attachment Upload ---------- #

class AttachmentResult(BaseModel):
    """Per-file upload result."""
    id: Optional[UUID] = None
    filename: str
    attached: bool
    message: str
    ml_response: Optional[Dict[str, Any]] = None


class AttachmentUploadResponse(BaseModel):
    """Overall response for the attachment upload endpoint."""
    session_id: str
    results: List[AttachmentResult]
