"""Tests for user upload service guardrails."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.uploads.user_upload_service import UserUploadService


def _build_service() -> tuple[UserUploadService, AsyncMock, AsyncMock]:
    redis_client = AsyncMock()
    openai_client = AsyncMock()
    service = UserUploadService(redis_client=redis_client, openai_client=openai_client)
    return service, redis_client, openai_client


@pytest.mark.anyio
async def test_rejects_tier_below_three() -> None:
    """Uploads should be blocked for users below Tier 3."""
    service, _, _ = _build_service()

    with pytest.raises(ValueError, match="starting from Tier 3"):
        await service.process_upload(
            file_content=b"hello world",
            filename="sample.pdf",
            session_id="session-a",
            tier_id=2,
            content_type="application/pdf",
        )


@pytest.mark.anyio
async def test_rejects_when_quota_reservation_hits_doc_limit() -> None:
    """Atomic reservation should reject when the session doc count is full."""
    service, redis_client, _ = _build_service()
    redis_client.eval.return_value = [0, "count_limit", 3, 1200]

    with pytest.raises(ValueError, match="Document limit reached"):
        await service.process_upload(
            file_content=b"hello world",
            filename="sample.png",
            session_id="session-b",
            tier_id=3,
            content_type="image/png",
        )


@pytest.mark.anyio
async def test_rejects_when_quota_reservation_hits_token_limit() -> None:
    """Atomic reservation should reject when token budget is exceeded."""
    service, redis_client, _ = _build_service()
    redis_client.eval.return_value = [0, "token_limit", 1, 50000]

    with pytest.raises(ValueError, match="Document too big"):
        await service.process_upload(
            file_content=b"hello world",
            filename="sample.png",
            session_id="session-c",
            tier_id=3,
            content_type="image/png",
        )


@pytest.mark.anyio
async def test_uses_unique_attachment_key_for_same_filename() -> None:
    """Service should not overwrite Redis mapping when filenames are reused."""
    service, redis_client, openai_client = _build_service()
    redis_client.eval.return_value = [1, "ok", 1, 100]
    openai_client.files.create = AsyncMock(return_value=SimpleNamespace(id="file_123"))
    redis_client.setex = AsyncMock()

    # Stub fitz so neither the metadata scrub nor the domain-validation text
    # extraction require PyMuPDF to be installed in the test environment.
    fake_doc = MagicMock()
    fake_doc.__enter__ = lambda s: s
    fake_doc.__exit__ = MagicMock(return_value=False)
    fake_doc.metadata = {}
    fake_doc.tobytes.return_value = b"hello world"
    fake_doc.page_count = 1
    fake_doc.load_page.return_value = MagicMock(get_text=MagicMock(return_value="financial data"))

    with patch("src.services.uploads.user_upload_service.uuid.uuid4", return_value="fixed-id"), \
         patch("src.services.uploads.user_upload_service.fitz") as mock_fitz:
        mock_fitz.open.return_value = fake_doc
        result = await service.process_upload(
            file_content=b"hello world",
            filename="report.pdf",
            session_id="session-d",
            tier_id=3,
            content_type="application/pdf",
        )

    assert result["file_id"] == "file_123"
    assert result["attachment_id"] == "fixed-id"
    redis_client.setex.assert_awaited_once()
    call_args = redis_client.setex.await_args.args
    assert call_args[0] == "openai_file:session-d:fixed-id"


@pytest.mark.anyio
async def test_tier3_token_cap_uses_min_of_ratio_and_static_cap() -> None:
    """Tier 3 cap should be min(25% model context, 35k static cap)."""
    service, _, _ = _build_service()
    limits = await service.get_limits_for_tier(3)
    assert limits["max_document_tokens"] == 35000


@pytest.mark.anyio
async def test_tier4_token_cap_uses_min_of_ratio_and_static_cap() -> None:
    """Tier 4 cap should be min(35% model context, 45k static cap)."""
    service, _, _ = _build_service()
    limits = await service.get_limits_for_tier(4)
    assert limits["max_document_tokens"] == 45000
