"""User document upload API routes."""

import asyncio

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Header,
                     HTTPException, UploadFile)
from fastapi.responses import JSONResponse

from src.api.dependencies import get_user_upload_service
from src.services.uploads.user_upload_service import UserUploadService
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def schedule_file_deletion(
    service: UserUploadService, file_id: str, delay_seconds: int = 7200
) -> None:
    """Wait for a delay and then delete the file from OpenAI.

    Defaults to 7200 seconds (2 hours).
    """
    await asyncio.sleep(delay_seconds)
    await service.delete_uploaded_file(file_id)


@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    _user_id: str = Header(..., alias="x-user-id"),
    session_id: str = Header(..., alias="x-session-id"),
    tier_id: int = Header(default=1, alias="x-tier-id"),
    service: UserUploadService = Depends(get_user_upload_service),
):
    """Upload multiple documents for direct OpenAI analysis.

    Available to Tier 3 and Tier 4 Institutional users.
    Requires 'x-user-id', 'x-session-id', and 'x-tier-id' headers.
    """
    try:
        if tier_id < 3:
            raise HTTPException(
                status_code=403,
                detail="Document uploads are available starting from Tier 3.",
            )

        limits = await service.get_limits_for_tier(tier_id)
        max_files = limits["max_files_per_request"]
        if len(files) > max_files:
            raise HTTPException(
                status_code=413,
                detail=f"Too many files in one request. Tier {tier_id} supports up to {max_files} files per upload.",
            )

        results = []
        for file in files:
            content = await file.read()
            try:
                result = await service.process_upload(
                    file_content=content,
                    filename=file.filename or "unnamed_file",
                    session_id=session_id,
                    tier_id=tier_id,
                    content_type=file.content_type,
                )
                background_tasks.add_task(
                    schedule_file_deletion, service, result["file_id"]
                )
                results.append(
                    {
                        "filename": file.filename,
                        "file_id": result.get("file_id") or result.get("attachment_id"),
                        "attachment_id": result.get("attachment_id"),
                        "strategy": result["strategy"],
                    }
                )
            finally:
                await file.close()

        return {
            "success": True,
            "size_too_large": False,
            "status": "success",
            "count": len(results),
            "files": results,
            "message": f"Successfully attached {len(results)} document(s) for direct analysis.",
        }

    except ValueError as e:
        msg = str(e)
        size_too_large = "too big" in msg.lower() or "size exceeds" in msg.lower()
        if size_too_large:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "size_too_large": True,
                    "status": "failed",
                    "message": msg,
                },
            )
        if "limit reached" in msg.lower():
            raise HTTPException(status_code=403, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except (TypeError, OSError, RuntimeError) as e:
        logger.error("[UPLOAD_API_ERROR] %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during document processing."
        ) from e
