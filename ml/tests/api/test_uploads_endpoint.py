"""Endpoint-function tests for user upload workflow."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from src.api.routes.uploads import upload_documents


class FakeUploadFile:
    """Minimal async UploadFile-compatible test double."""

    def __init__(self, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        """Return file bytes once."""
        return self._content

    async def close(self) -> None:
        """No-op close for test compatibility."""
        return None


def _make_upload_file(name: str, content: bytes, content_type: str) -> FakeUploadFile:
    """Build a fake UploadFile object for endpoint tests."""
    return FakeUploadFile(filename=name, content=content, content_type=content_type)


@pytest.mark.anyio
async def test_upload_accepts_multiple_files_in_single_request() -> None:
    """Endpoint should process multiple files in one call."""
    service = SimpleNamespace()
    service.get_limits_for_tier = AsyncMock(return_value={"max_files_per_request": 3})
    service.process_upload = AsyncMock(
        side_effect=[
            {"strategy": "openai_direct", "file_id": "file_a"},
            {"strategy": "openai_direct", "file_id": "file_b"},
        ]
    )
    service.delete_uploaded_file = AsyncMock(return_value=True)

    response = await upload_documents(
        background_tasks=BackgroundTasks(),
        files=[
            _make_upload_file("a.pdf", b"a-content", "application/pdf"),
            _make_upload_file("b.pdf", b"b-content", "application/pdf"),
        ],
        _user_id="user-1",
        session_id="session-1",
        tier_id=3,
        service=service,
    )

    assert response["status"] == "success"
    assert response["count"] == 2
    assert len(response["files"]) == 2
    assert service.process_upload.await_count == 2


@pytest.mark.anyio
async def test_upload_rejects_tier_below_three() -> None:
    """Tier 0/1/2 should be blocked before file processing."""
    service = SimpleNamespace()
    service.get_limits_for_tier = AsyncMock()
    service.process_upload = AsyncMock()
    service.delete_uploaded_file = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as caught:
        await upload_documents(
            background_tasks=BackgroundTasks(),
            files=[_make_upload_file("a.pdf", b"a-content", "application/pdf")],
            _user_id="user-1",
            session_id="session-1",
            tier_id=2,
            service=service,
        )

    assert caught.value.status_code == 403
    service.process_upload.assert_not_called()


@pytest.mark.anyio
async def test_upload_rejects_when_request_count_exceeds_limit() -> None:
    """Tier limit should reject too many files in one upload request."""
    service = SimpleNamespace()
    service.get_limits_for_tier = AsyncMock(return_value={"max_files_per_request": 1})
    service.process_upload = AsyncMock()
    service.delete_uploaded_file = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as caught:
        await upload_documents(
            background_tasks=BackgroundTasks(),
            files=[
                _make_upload_file("a.pdf", b"a-content", "application/pdf"),
                _make_upload_file("b.pdf", b"b-content", "application/pdf"),
            ],
            _user_id="user-1",
            session_id="session-1",
            tier_id=3,
            service=service,
        )

    assert caught.value.status_code == 413
    service.process_upload.assert_not_called()


@pytest.mark.anyio
async def test_upload_maps_size_violation_to_size_flags() -> None:
    """Size violations should return explicit size flags for client UX."""
    service = SimpleNamespace()
    service.get_limits_for_tier = AsyncMock(return_value={"max_files_per_request": 3})
    service.process_upload = AsyncMock(side_effect=ValueError("File size exceeds limit"))
    service.delete_uploaded_file = AsyncMock(return_value=True)

    response = await upload_documents(
        background_tasks=BackgroundTasks(),
        files=[_make_upload_file("a.pdf", b"a-content", "application/pdf")],
        _user_id="user-1",
        session_id="session-1",
        tier_id=3,
        service=service,
    )

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["success"] is False
    assert payload["size_too_large"] is True
    assert payload["status"] == "failed"


@pytest.mark.anyio
async def test_upload_maps_doc_limit_violation_to_403() -> None:
    """ValueError with doc-limit semantics should map to 403."""
    service = SimpleNamespace()
    service.get_limits_for_tier = AsyncMock(return_value={"max_files_per_request": 3})
    service.process_upload = AsyncMock(side_effect=ValueError("Document limit reached"))
    service.delete_uploaded_file = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as caught:
        await upload_documents(
            background_tasks=BackgroundTasks(),
            files=[_make_upload_file("a.pdf", b"a-content", "application/pdf")],
            _user_id="user-1",
            session_id="session-1",
            tier_id=3,
            service=service,
        )

    assert caught.value.status_code == 403
