import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from io import BytesIO
from typing import List
from uuid import UUID

import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.chat import (
    Attachment,
    ChatMessage,
    ChatSession,
    MessageAttachment,
    UsageCounter,
)
from app.models.users import User
from app.schemas.chat import (
    AttachmentResult,
    AttachmentUploadResponse,
    ChatMessageCreate,
    ChatSessionCreate,
)
from app.services.s3_service import s3_service
from app.services.token_service import TokenService


class ChatService:
    @staticmethod
    def create_session(
        db: Session, user_id: int, session_in: ChatSessionCreate
    ) -> ChatSession:
        db_session = ChatSession(
            user_id=user_id, title=session_in.title, model=session_in.model
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        if session_in.first_message:
            message_in = ChatMessageCreate(
                role="user", content=session_in.first_message
            )
            ChatService.create_message(
                db,
                session_id=db_session.session_id,
                user_id=user_id,
                message_in=message_in,
            )
            db.refresh(db_session)

        return db_session

    @staticmethod
    def get_sessions(db: Session, user_id: int) -> list[ChatSession]:
        return (
            db.query(ChatSession)
            .options(
                joinedload(ChatSession.messages).joinedload(ChatMessage.attachments)
            )
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.started_at.desc())
            .all()
        )

    @staticmethod
    def get_session(db: Session, session_id: UUID, user_id: int) -> ChatSession:
        session = (
            db.query(ChatSession)
            .options(
                joinedload(ChatSession.messages).joinedload(ChatMessage.attachments)
            )
            .filter(
                ChatSession.session_id == session_id, ChatSession.user_id == user_id
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    @staticmethod
    def delete_session(db: Session, session_id: UUID, user_id: int):
        session = ChatService.get_session(db, session_id, user_id)

        db.delete(session)
        db.commit()

        return {"status": "success", "message": "Session deleted"}

    @staticmethod
    def create_message(
        db: Session, session_id: UUID, user_id: int, message_in: ChatMessageCreate
    ) -> ChatMessage:

        session = ChatService.get_session(db, session_id, user_id)

        db_message = ChatMessage(
            session_id=session.id,
            role=message_in.role,
            content=message_in.content,
            non_substantive=message_in.non_substantive,
        )
        db.add(db_message)
        db.flush()

        if message_in.attachment_ids:
            for attr_id in message_in.attachment_ids:
                msg_attr = MessageAttachment(
                    message_id=db_message.id, attachment_id=attr_id
                )
                db.add(msg_attr)
            db_message.has_attachments = True

        if message_in.role == "user" and not message_in.non_substantive:
            ChatService.increment_usage(db, user_id)

            if not session.title:
                preview = (
                    message_in.content[:50] + "..."
                    if len(message_in.content) > 50
                    else message_in.content
                )
                session.title = preview
                db.add(session)

        db.commit()
        db.refresh(db_message)

        return db_message

    @staticmethod
    async def create_message_stream(
        db: Session,
        session_id: str,
        user_id: int,
        message_in: ChatMessageCreate,
        tier_level: int,
    ) -> AsyncGenerator[str, None]:
        print(f"--- Service: create_message_stream [GENERATOR START] ---", flush=True)
        try:
            print(f"--- Service: Calling _handle_session_creation ---", flush=True)
            (
                real_session_id,
                is_new,
                session_event,
            ) = await ChatService._handle_session_creation(
                db, session_id, user_id, message_in
            )
            print(
                f"--- Service: _handle_session_creation done. is_new={is_new} ---",
                flush=True,
            )

            if session_event:
                print(f"--- Service: Yielding session_event ---", flush=True)
                yield session_event

            print(
                f"--- Service: Calling create_message (saving user message) ---",
                flush=True,
            )
            db_message = ChatService.create_message(
                db, real_session_id, user_id, message_in
            )
            print(
                f"--- Service: user message saved. db_id={db_message.id} ---",
                flush=True,
            )

            print(f"--- Service: Starting ML response stream ---", flush=True)
            async for chunk in ChatService._stream_ml_response(
                db,
                db_message.session,
                real_session_id,
                is_new,
                message_in.content,
                user_id,
                tier_level,
            ):
                yield chunk
            print(f"--- Service: ML response stream finished ---", flush=True)
        except Exception as e:
            print(
                f"--- Service: ERROR in create_message_stream: {str(e)} ---", flush=True
            )
            import traceback

            traceback.print_exc()
            yield f"data: {json.dumps({'error': 'Internal server error during streaming'})}\n\n"

    @staticmethod
    async def create_trial_message_stream(
        db: Session,
        message_in: ChatMessageCreate,
    ) -> AsyncGenerator[str, None]:
        """
        Stream ML response for trial (guest) users.
        Sets tier to 0 and does not persist to database.
        """
        print(f"--- Service: create_trial_message_stream [TRIAL] ---", flush=True)
        try:
            # Use a dummy session ID for the trial
            trial_session_id = "trial-session"

            async for chunk in ChatService._stream_trial_ml_response(
                message_in.content, trial_session_id
            ):
                yield chunk
            print(f"--- Service: Trial ML response stream finished ---", flush=True)
        except Exception as e:
            print(
                f"--- Service: ERROR in create_trial_message_stream: {str(e)} ---",
                flush=True,
            )
            yield f"data: {json.dumps({'error': 'Internal server error during trial streaming'})}\n\n"

    @staticmethod
    async def _stream_trial_ml_response(
        user_message: str, session_id: str
    ) -> AsyncGenerator[str, None]:
        # Tier 0 for trial users as requested
        payload = {
            "is_new": True,
            "session_id": session_id,
            "user_message": user_message,
            "user_id": "trial",
            "tier": 0,
        }

        async with httpx.AsyncClient() as client:
            try:
                print(
                    f"--- Service: Connecting to ML API (TRIAL): {settings.ML_API_URL}/api/v1/chat/stream ---",
                    flush=True,
                )
                async with client.stream(
                    "POST",
                    f"{settings.ML_API_URL}/api/v1/chat/stream",
                    json=payload,
                    timeout=60.0,
                ) as response:
                    if response.status_code != 200:
                        detail = await response.aread()
                        yield f"data: {json.dumps({'error': detail.decode()})}\n\n"
                        return

                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk

                    yield "data: [DONE]\n\n"

            except httpx.HTTPError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    @staticmethod
    async def _handle_session_creation(
        db: Session, session_id: str, user_id: int, message_in: ChatMessageCreate
    ):
        print(f"--- Service: _handle_session_creation ---", flush=True)
        if session_id == "null":
            print(f"Creating new session for user {user_id}", flush=True)
            db_session = ChatSession(
                user_id=user_id, model=message_in.model or "standard"
            )
            db.add(db_session)
            db.commit()
            db.refresh(db_session)

            session_event = f"data: {json.dumps({'type': 'session_id', 'data': str(db_session.session_id)})}\n\n"
            print(f"New session ID: {db_session.session_id}", flush=True)
            return db_session.session_id, True, session_event

        try:
            print(f"Using existing session ID: {session_id}", flush=True)
            return UUID(session_id), False, None
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid session ID format"
            ) from exc

    @staticmethod
    async def _stream_ml_response(
        db: Session,
        session: ChatSession,
        session_id: UUID,
        is_new: bool,
        user_message: str,
        user_id: int,
        tier: int,
    ) -> AsyncGenerator[str, None]:

        payload = {
            "is_new": is_new,
            "session_id": str(session_id),
            "user_message": user_message,
            "user_id": str(user_id),
            "tier": tier,
        }

        full_response = ""
        total_tokens = 0

        print("TIer", tier)
        print("User_id", user_id)

        async with httpx.AsyncClient() as client:
            try:
                print(
                    f"--- Service: Connecting to ML API: {settings.ML_API_URL}/api/v1/chat/stream ---",
                    flush=True,
                )
                print(f"Payload: {payload}", flush=True)
                async with client.stream(
                    "POST",
                    f"{settings.ML_API_URL}/api/v1/chat/stream",
                    json=payload,
                    timeout=60.0,
                ) as response:
                    print(f"ML API Response Status: {response.status_code}", flush=True)

                    if response.status_code != 200:
                        detail = await response.aread()
                        print(
                            f"--- Service: ML API returned ERROR: {detail.decode()} ---",
                            flush=True,
                        )
                        yield f"data: {json.dumps({'error': detail.decode()})}\n\n"
                        return

                    suggested_follow_ups = []
                    sources = []

                    print(
                        f"--- Service: Starting to iterate chunks from ML API ---",
                        flush=True,
                    )
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk

                            for line in chunk.split("\n"):
                                line = line.strip()
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    if data_str != "[DONE]":
                                        try:
                                            data_json = json.loads(data_str)
                                            dtype = data_json.get("type")
                                            ddata = data_json.get("data")

                                            if dtype == "content":
                                                full_response += ddata or ""
                                            elif dtype == "content_block_delta":
                                                full_response += ddata or ""
                                            elif dtype == "sources":
                                                if isinstance(ddata, list):
                                                    sources.extend(ddata)
                                            elif dtype == "metadata":
                                                data_inner = (
                                                    ddata
                                                    if isinstance(ddata, dict)
                                                    else {}
                                                )
                                                if "suggested_follow_ups" in data_inner:
                                                    suggested_follow_ups = data_inner[
                                                        "suggested_follow_ups"
                                                    ]
                                                if "sources" in data_inner:
                                                    sources.extend(
                                                        data_inner["sources"]
                                                    )

                                            extracted_tokens = (
                                                ChatService._extract_total_tokens(
                                                    data_json
                                                )
                                            )
                                            if extracted_tokens is not None:
                                                total_tokens = extracted_tokens
                                        except json.JSONDecodeError:
                                            continue

                    print(
                        f"--- Service: Finished iterating chunks from ML API ---",
                        flush=True,
                    )

                if full_response:
                    if sources:
                        full_response += "\n\n### Sources\n"
                        for s in sources:
                            title = s.get("id") or s.get("source") or "Source"
                            url = s.get("url") or "#"
                            full_response += f"- [{title}]({url})\n"

                    if suggested_follow_ups:
                        full_response += "\n\n### Suggested Questions\n"
                        for q in suggested_follow_ups:
                            full_response += f"- {q}\n"

                    bot_message = ChatService._save_bot_message(
                        db, session, session_id, full_response, suggested_follow_ups
                    )
                    if total_tokens > 0:
                        ChatService._record_chat_token_usage(
                            db,
                            user_id=user_id,
                            tokens_used=total_tokens,
                            chat_message_id=bot_message.id,
                        )
                    yield "data: [DONE]\n\n"

            except httpx.HTTPError as exc:
                print(
                    f"--- Service: ML API Connection Error: {str(exc)} ---", flush=True
                )
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    @staticmethod
    def _extract_content(chunk: str) -> str:
        result = ""
        for line in chunk.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str != "[DONE]":
                    try:
                        data_json = json.loads(data_str)
                        if data_json.get("type") == "content":
                            result += data_json.get("data", "")
                    except json.JSONDecodeError:
                        continue
        return result

    @staticmethod
    def _extract_total_tokens(data: dict) -> int | None:
        def coerce_token_value(value) -> int | None:
            if isinstance(value, bool):
                return None
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str) and value.isdigit():
                return int(value)
            return None

        total = coerce_token_value(data.get("total_tokens"))
        if total is not None:
            return total

        nested = data.get("data")
        if isinstance(nested, dict):
            total = coerce_token_value(nested.get("total_tokens"))
            if total is not None:
                return total

            usage = nested.get("usage")
            if isinstance(usage, dict):
                total = coerce_token_value(usage.get("total_tokens"))
                if total is not None:
                    return total

        usage = data.get("usage")
        if isinstance(usage, dict):
            return coerce_token_value(usage.get("total_tokens"))

        return None

    @staticmethod
    def _save_bot_message(
        db: Session,
        session: ChatSession,
        session_id: UUID,
        content: str,
        suggested_follow_ups: list[str] = None,
    ):
        print(f"--- Service: _save_bot_message ---", flush=True)
        print(f"Saving bot response ({len(content)} chars) to DB", flush=True)
        bot_msg = ChatMessage(
            session_id=session.id, role="bot", content=content, non_substantive=False
        )
        db.add(bot_msg)
        db.commit()
        db.refresh(bot_msg)
        return bot_msg

    @staticmethod
    def _record_chat_token_usage(
        db: Session,
        user_id: int,
        tokens_used: int,
        chat_message_id: int,
    ) -> None:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        TokenService.deduct_tokens_for_chat(
            db,
            user,
            tokens_used,
            chat_message_id=chat_message_id,
            description="Chat response token usage",
            extra_metadata={
                "source": "chat_stream",
                "total_tokens": tokens_used,
            },
        )
        db.commit()

    @staticmethod
    def increment_usage(db: Session, user_id: int):
        today = date.today()
        counter = (
            db.query(UsageCounter)
            .filter(UsageCounter.user_id == user_id, UsageCounter.date == today)
            .first()
        )

        if not counter:
            counter = UsageCounter(user_id=user_id, date=today, messages_used=1)
        else:
            counter.messages_used += 1

        db.add(counter)

    @staticmethod
    def get_usage(db: Session, user_id: int) -> UsageCounter:
        today = date.today()
        counter = (
            db.query(UsageCounter)
            .filter(UsageCounter.user_id == user_id, UsageCounter.date == today)
            .first()
        )

        if not counter:
            return UsageCounter(user_id=user_id, date=today, messages_used=0)

        return counter

    # ------------------------------------------------------------------ #
    #  Attachment upload                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def upload_attachments(
        db: Session,
        session_id: str,
        user_id: int,
        tier: int,
        files: list[UploadFile],
    ) -> AttachmentUploadResponse:
        results: list[AttachmentResult] = []
        files_info = []
        files_payload = []

        # 1. Read files and prepare payload
        for file in files:
            filename = file.filename or "unknown"
            content_type = file.content_type or "application/octet-stream"
            raw_bytes = await file.read()
            files_info.append(
                {"filename": filename, "content_type": content_type, "bytes": raw_bytes}
            )
            files_payload.append(("files", (filename, raw_bytes, content_type)))

        # 2. Call ML API
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                headers = {
                    "x-user-id": str(user_id),
                    "x-session-id": str(session_id),
                    "x-tier-id": str(tier),
                }

                print(
                    f"[upload_attachments] Forwarding {len(files)} file(s) to ML API. "
                    f"Session: {session_id}",
                    flush=True,
                )

                response = await client.post(
                    f"{settings.ML_API_URL}/api/v1/upload",
                    headers=headers,
                    files=files_payload,
                )

                print(
                    f"[upload_attachments] ML API status={response.status_code}",
                    flush=True,
                )

                if response.status_code != 200:
                    error_detail = response.text
                    print(
                        f"[upload_attachments] ML API error detail: {error_detail}",
                        flush=True,
                    )
                    for info in files_info:
                        results.append(
                            AttachmentResult(
                                filename=info["filename"],
                                attached=False,
                                message=f"ML API returned HTTP {response.status_code}: {error_detail[:100]}",
                            )
                        )
                    return AttachmentUploadResponse(
                        session_id=session_id, results=results
                    )

                ml_data: dict = response.json()
                success = bool(ml_data.get("success", False))
                size_too_large = bool(ml_data.get("size_too_large", False))
                ml_files_results = ml_data.get("files", [])

                if not (success and not size_too_large):
                    msg = ml_data.get(
                        "message", "The ML service could not process this file."
                    )
                    if size_too_large:
                        msg = "File is too large and could not be attached."

                    for info in files_info:
                        results.append(
                            AttachmentResult(
                                filename=info["filename"],
                                attached=False,
                                message=msg,
                                ml_response=ml_data,
                            )
                        )
                    return AttachmentUploadResponse(
                        session_id=session_id, results=results
                    )

                # 3. ML Success - now save to S3 and DB
                if ml_files_results:
                    for ml_file in ml_files_results:
                        ml_filename = ml_file.get("filename", "unknown")
                        info = next(
                            (i for i in files_info if i["filename"] == ml_filename),
                            None,
                        )
                        if info:
                            res = await ChatService._process_and_save_attachment(
                                db, user_id, session_id, info
                            )
                            res.ml_response = ml_file
                            results.append(res)
                else:
                    # Generic success for all files
                    for info in files_info:
                        res = await ChatService._process_and_save_attachment(
                            db, user_id, session_id, info
                        )
                        res.ml_response = ml_data
                        results.append(res)

            except httpx.HTTPError as exc:
                print(f"[upload_attachments] HTTP error: {exc}", flush=True)
                for info in files_info:
                    results.append(
                        AttachmentResult(
                            filename=info["filename"],
                            attached=False,
                            message=f"Connection error to ML service: {exc}",
                        )
                    )
            except Exception as exc:
                print(f"[upload_attachments] Unexpected error: {exc}", flush=True)
                for info in files_info:
                    results.append(
                        AttachmentResult(
                            filename=info["filename"],
                            attached=False,
                            message=f"Unexpected error: {exc}",
                        )
                    )

        return AttachmentUploadResponse(
            session_id=session_id,
            results=results,
        )

    @staticmethod
    async def _process_and_save_attachment(
        db: Session, user_id: int, session_id: str, info: dict
    ) -> AttachmentResult:
        filename = info["filename"]
        raw_bytes = info["bytes"]
        content_type = info["content_type"]

        # 1. Calculate checksum
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # Check if file already exists for this user
        existing = (
            db.query(Attachment)
            .filter(
                Attachment.user_id == user_id,
                Attachment.checksum == checksum,
                Attachment.status == "ready",
            )
            .first()
        )

        if existing:
            print(
                f"[upload_attachments] File already exists (checksum: {checksum}), reusing ID: {existing.id}",
                flush=True,
            )
            return AttachmentResult(
                id=existing.id,
                filename=filename,
                attached=True,
                message="File successfully attached to the chat (reused).",
            )

        # 2. Upload to S3
        today_str = date.today().isoformat()
        file_uuid = uuid.uuid4()
        s3_key = f"chat-attachments/{user_id}/{session_id}/{today_str}/{file_uuid}_{filename}"

        print(f"[upload_attachments] Uploading to S3: {s3_key}", flush=True)
        storage_url = await s3_service.upload_fileobj(
            BytesIO(raw_bytes), s3_key, content_type
        )

        # 3. Save to DB
        db_attachment = Attachment(
            id=file_uuid,
            user_id=user_id,
            file_name=filename,
            file_type=content_type,
            file_size=len(raw_bytes),
            storage_url=storage_url,
            storage_provider="s3",
            checksum=checksum,
            status="ready",
        )
        db.add(db_attachment)
        try:
            db.commit()
            db.refresh(db_attachment)
        except Exception as e:
            print(f"[upload_attachments] DB error: {e}", flush=True)
            db.rollback()
            return AttachmentResult(
                filename=filename,
                attached=False,
                message=f"Failed to save attachment metadata to database: {str(e)}",
            )

        return AttachmentResult(
            id=db_attachment.id,
            filename=filename,
            attached=True,
            message="File successfully attached to the chat.",
        )
