from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.models.users import User
from app.schemas.chat import (
    AttachmentUploadResponse,
    ChatMessageCreate,
    ChatSession,
    ChatSessionCreate,
    ChatUsage,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


@router.post("/sessions", response_model=ChatSession)
def create_session(
    session_in: ChatSessionCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return ChatService.create_session(db, user_id=current_user.id, session_in=session_in)


@router.get("/sessions", response_model=List[ChatSession])
def get_sessions(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return ChatService.get_sessions(db, user_id=current_user.id)


@router.get("/sessions/{session_id}", response_model=ChatSession)
def get_session(
    session_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return ChatService.get_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
    )


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return ChatService.delete_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
    )


@router.post("/sessions/{session_id}/messages")
async def create_message(
    session_id: str,
    message_in: ChatMessageCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    print(f"--- API: create_message ---", flush=True)
    print(f"Session ID: {session_id}", flush=True)
    print(f"User ID: {current_user.id}", flush=True)
    print(f"Message preview: {message_in.content[:50]}...", flush=True)

    print(f"--- API: Calling ChatService.create_message_stream ---", flush=True)
    response = StreamingResponse(
        ChatService.create_message_stream(
            db,
            session_id=session_id,
            user_id=current_user.id,
            message_in=message_in,
            tier_level = current_user.subscription.tier.level
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    print(f"--- API: Returning StreamingResponse (200 OK headers sent) ---", flush=True)
    return response


@router.post("/trial/stream")
async def create_trial_message(
    message_in: ChatMessageCreate,
    db: Session = Depends(deps.get_db),
):
    """
    Public endpoint for trial chat messages.
    Does not require authentication.
    """
    response = StreamingResponse(
        ChatService.create_trial_message_stream(
            db,
            message_in=message_in
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    return response


@router.get("/usage", response_model=ChatUsage)
def get_usage(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    return ChatService.get_usage(db, user_id=current_user.id)


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=AttachmentUploadResponse,
    summary="Upload attachments to a chat session",
)
async def upload_attachments(
    session_id: str,
    files: List[UploadFile] = File(..., description="One or more files to attach"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Upload one or more files to be attached to a chat session.

    Each file is forwarded to the ML service at ``/api/v1/upload`` together
    with the ``session_id``, ``user_id``, and the user's ``tier`` level.

    **Per-file result rules**
    - `attached: true`  → ML returned `success=true` and `size_too_large=false`
    - `attached: false` → file too large, ML processing failed, or a network error
    """
    tier = current_user.subscription.tier.level

    return await ChatService.upload_attachments(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        tier=tier,
        files=files,
    )
