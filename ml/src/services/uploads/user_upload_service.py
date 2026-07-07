"""User document upload service."""

import asyncio
import base64
import io
import json
import uuid
from typing import Any

import fitz  # PyMuPDF
import pandas as pd
from openai import AsyncOpenAI
from src.llm.fallback_client import FallbackAsyncOpenAI

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

TIER3_ALLOWED_TYPES = frozenset(
    {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
)
TIER4_ALLOWED_TYPES = frozenset(TIER3_ALLOWED_TYPES | {".xlsx", ".xls", ".csv"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
SPREADSHEET_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv"})
MODEL_CONTEXT_WINDOWS = {
    "gpt-4.1": 1047576,
    "gpt-4.1-mini": 1047576,
    "gpt-4.1-nano": 1047576,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-5": 400000,
    "gpt-5-mini": 400000,
    "gpt-5-nano": 400000,
    "gpt-5.2": 400000,
}
DEFAULT_MODEL_CONTEXT_WINDOW = 128000
UPLOAD_RESERVE_LUA = """
local count_key = KEYS[1]
local tokens_key = KEYS[2]
local count_limit = tonumber(ARGV[1])
local token_limit = tonumber(ARGV[2])
local token_delta = tonumber(ARGV[3])
local ttl_seconds = tonumber(ARGV[4])

local current_count = tonumber(redis.call('GET', count_key) or '0')
local current_tokens = tonumber(redis.call('GET', tokens_key) or '0')

if (current_count + 1) > count_limit then
  return {0, 'count_limit', current_count, current_tokens}
end

if (current_tokens + token_delta) > token_limit then
  return {0, 'token_limit', current_count, current_tokens}
end

local next_count = redis.call('INCR', count_key)
redis.call('EXPIRE', count_key, ttl_seconds)
local next_tokens = redis.call('INCRBY', tokens_key, token_delta)
redis.call('EXPIRE', tokens_key, ttl_seconds)

return {1, 'ok', next_count, next_tokens}
"""

UPLOAD_ROLLBACK_LUA = """
local count_key = KEYS[1]
local tokens_key = KEYS[2]
local token_delta = tonumber(ARGV[1])

local current_count = tonumber(redis.call('GET', count_key) or '0')
if current_count > 0 then
  redis.call('DECR', count_key)
end

local current_tokens = tonumber(redis.call('GET', tokens_key) or '0')
if current_tokens > 0 then
  local updated = current_tokens - token_delta
  if updated < 0 then
    updated = 0
  end
  redis.call('SET', tokens_key, updated)
end

return 1
"""


class UserUploadService:
    """Service for handling user-uploaded documents with tier enforcement via OpenAI Files API."""

    def __init__(self, redis_client: Any, openai_client: AsyncOpenAI | FallbackAsyncOpenAI) -> None:
        """Initialize with Redis and OpenAI clients."""
        self.redis_client = redis_client
        self.openai_client = openai_client

    @staticmethod
    def _mask_id(id_val: str) -> str:
        """Mask ID for logging."""
        return f"{id_val[:4]}***{id_val[-4:]}" if len(id_val) > 8 else id_val

    async def process_upload(
        self,
        file_content: bytes,
        filename: str,
        *,
        session_id: str,
        tier_id: int,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """Process a document upload by sending it to OpenAI and storing the reference.

        Args:
            file_content: Raw bytes of the uploaded file.
            filename: Original filename.
            session_id: Session ID for scoping.
            tier_id: The user's tier for entitlement checking.
        """
        if tier_id < 3:
            logger.warning(
                "[UPLOAD_REJECTED] Tier: %d | Reason: tier_not_eligible", tier_id
            )
            raise ValueError("Document uploads are available starting from Tier 3.")

        limits = self._limits_for_tier(tier_id)

        if len(file_content) > limits["max_upload_size_bytes"]:
            logger.warning("[UPLOAD_REJECTED] File too large: %s", filename)
            raise ValueError(
                f"File size exceeds limit of {limits['max_upload_size_bytes']} bytes"
            )

        ext = self._validate_upload(filename, tier_id)
        self._validate_content_type(ext, content_type)

        # Offload token estimation to a separate thread to avoid blocking the event loop
        estimated_tokens = await asyncio.to_thread(
            self._estimate_tokens, file_content, ext
        )
        reserve = await self._reserve_upload_quota(
            count_key=f"session_docs:{session_id}",
            tokens_key=f"session_tokens:{session_id}",
            max_docs_per_session=limits["max_docs_per_session"],
            max_document_tokens=limits["max_document_tokens"],
            estimated_tokens=estimated_tokens,
        )
        if not reserve["allowed"]:
            if reserve["reason"] == "count_limit":
                logger.warning(
                    "[UPLOAD_REJECTED] Doc limit reached for session %s",
                    self._mask_id(session_id),
                )
                raise ValueError(
                    "Document limit reached. You can only upload "
                    f"{limits['max_docs_per_session']} documents per session."
                )

            logger.warning(
                "[UPLOAD_REJECTED] Token limit exceeded for session %s",
                self._mask_id(session_id),
            )
            raise ValueError(
                "Document too big. The total size of attached documents exceeds the session limit."
            )

        logger.info(
            "[UPLOAD_START] File: %s | Estimated Tokens: %d | Session: %s",
            filename,
            estimated_tokens,
            self._mask_id(session_id),
        )

        try:
            if ext in IMAGE_EXTENSIONS:
                return await self._process_image_upload(
                    file_content,
                    filename,
                    session_id,
                    content_type=content_type,
                    ext=ext,
                )
            if ext in SPREADSHEET_EXTENSIONS:
                return await self._process_spreadsheet_upload(
                    file_content,
                    filename,
                    session_id,
                    content_type=content_type,
                    ext=ext,
                )
            return await self._process_document_upload(
                file_content, filename, session_id, content_type
            )

        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            await self._rollback_reserved_quota(
                count_key=f"session_docs:{session_id}",
                tokens_key=f"session_tokens:{session_id}",
                estimated_tokens=estimated_tokens,
            )
            logger.error(
                "[UPLOAD_FAILED] File: %s | Error: %s", filename, exc, exc_info=True
            )
            raise

    async def delete_uploaded_file(self, file_id: str | None) -> bool:
        """Delete a file from OpenAI's servers. Safe to call with None for non-OpenAI files.

        Args:
            file_id: The OpenAI file ID to delete, or None for base64/text files.
        """
        if not file_id:
            return True  # Nothing to delete from OpenAI (image/spreadsheet stored in Redis only)
        try:
            await self.openai_client.files.delete(file_id)
            logger.info("[FILE_DELETED] OpenAI File ID: %s", file_id)
            return True
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            logger.warning("[DELETE_FAILED] Failed to delete file %s: %s", file_id, exc)
            return False

    async def _process_image_upload(
        self,
        file_content: bytes,
        filename: str,
        session_id: str,
        *,
        content_type: str | None,
        ext: str,
    ) -> dict[str, Any]:
        """Store image as base64 in Redis. No OpenAI upload needed."""
        attachment_id = str(uuid.uuid4())
        mime = content_type or f"image/{ext.lstrip('.')}"
        base64_data = base64.b64encode(file_content).decode("utf-8")
        file_metadata = {
            "source": "base64",
            "file_id": None,
            "mime_type": mime,
            "base64_data": base64_data,
        }
        await self.redis_client.setex(
            f"openai_file:{session_id}:{attachment_id}",
            settings.openai_file_id_ttl_seconds,
            json.dumps(file_metadata),
        )
        logger.info("[UPLOAD_SUCCESS] Image stored as base64 in Redis: %s", filename)
        return {
            "strategy": "base64_inline",
            "file_id": None,
            "attachment_id": attachment_id,
            "mime_type": mime,
        }

    async def _process_spreadsheet_upload(
        self,
        file_content: bytes,
        filename: str,
        session_id: str,
        *,
        content_type: str | None,
        ext: str,
    ) -> dict[str, Any]:
        """Upload spreadsheet to OpenAI Files API for native analysis."""
        attachment_id = str(uuid.uuid4())
        file_id = (
            await self.openai_client.files.create(
                file=(filename, file_content), purpose="user_data"
            )
        ).id

        text = self._extract_spreadsheet_text(file_content, ext)
        if self._is_obviously_non_financial(text):
            logger.warning(
                "[UPLOAD_REJECTED] File: %s | Reason: non_financial_content", filename
            )
            raise ValueError(
                "Sorry, this is not a financial document so please upload a financial document."
            )

        file_metadata = {
            "source": "openai",
            "file_id": file_id,
            "mime_type": content_type
            or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        await self.redis_client.setex(
            f"openai_file:{session_id}:{attachment_id}",
            settings.openai_file_id_ttl_seconds,
            json.dumps(file_metadata),
        )
        logger.info(
            "[UPLOAD_SUCCESS] Spreadsheet uploaded to OpenAI: %s | File ID: %s",
            filename,
            file_id,
        )
        return {
            "strategy": "openai_direct",
            "file_id": file_id,
            "attachment_id": attachment_id,
            "mime_type": file_metadata["mime_type"],
        }

    async def _process_document_upload(
        self,
        file_content: bytes,
        filename: str,
        session_id: str,
        content_type: str | None,
    ) -> dict[str, Any]:
        """Upload PDF/Word document to OpenAI Files API and store file_id in Redis."""
        attachment_id = str(uuid.uuid4())

        # Scrub PDF metadata to prevent metadata injection
        if content_type == "application/pdf":
            try:
                fitz_open = getattr(fitz, "open")
                with fitz_open(stream=file_content, filetype="pdf") as doc:
                    doc.set_metadata({k: "" for k in doc.metadata.keys()})
                    file_content = doc.tobytes()
            except (ValueError, RuntimeError, OSError, AttributeError) as exc:
                logger.warning(
                    "[METADATA_SCRUB_FAILED] Failed to scrub PDF metadata: %s", exc
                )

        file_id = (
            await self.openai_client.files.create(
                file=(filename, file_content), purpose="user_data"
            )
        ).id
        # Pre-process for domain validation
        text = (
            self._extract_document_text(file_content, ".pdf")
            if (content_type == "application/pdf")
            else ""
        )
        if self._is_obviously_non_financial(text):
            logger.warning(
                "[UPLOAD_REJECTED] File: %s | Reason: non_financial_content", filename
            )
            raise ValueError(
                "Sorry, this is not a financial document so please upload a financial document."
            )

        file_metadata = {
            "source": "openai",
            "file_id": file_id,
            "mime_type": content_type or "application/pdf",
        }
        await self.redis_client.setex(
            f"openai_file:{session_id}:{attachment_id}",
            settings.openai_file_id_ttl_seconds,
            json.dumps(file_metadata),
        )
        logger.info(
            "[UPLOAD_SUCCESS] Document uploaded to OpenAI: %s | File ID: %s",
            filename,
            file_id,
        )
        return {
            "strategy": "openai_direct",
            "file_id": file_id,
            "attachment_id": attachment_id,
            "mime_type": file_metadata["mime_type"],
        }

    def _validate_upload(self, filename: str, tier_id: int) -> str:
        """Validate filename and tier entitlements, returning the extension."""
        ext = filename.lower()
        ext = ext[ext.rfind(".") :] if "." in ext else ""
        allowed_types = TIER4_ALLOWED_TYPES if tier_id >= 4 else TIER3_ALLOWED_TYPES
        if ext not in allowed_types:
            logger.warning(
                "[UPLOAD_REJECTED] Unsupported type %s for tier %d", ext, tier_id
            )
            raise ValueError(
                f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
            )
        return ext

    def _validate_content_type(self, ext: str, content_type: str | None) -> None:
        """Validate uploaded MIME type against extension-level allowlist."""
        if not content_type:
            return
        mime = content_type.lower().strip()
        allowed_mimes: dict[str, set[str]] = {
            ".pdf": {"application/pdf"},
            ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
            ".xls": {"application/vnd.ms-excel"},
            ".xlsx": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            },
            ".doc": {"application/msword"},
            ".docx": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            },
            ".jpg": {"image/jpeg"},
            ".jpeg": {"image/jpeg"},
            ".png": {"image/png"},
            ".webp": {"image/webp"},
            ".gif": {"image/gif"},
        }
        expected = allowed_mimes.get(ext)
        if expected and mime not in expected:
            raise ValueError(
                f"Invalid content type '{content_type}' for file extension '{ext}'"
            )

    def _limits_for_tier(self, tier_id: int) -> dict[str, int]:
        """Return upload guardrail settings for the given tier."""
        if tier_id >= 4:
            model_context_window = self._resolve_model_context_window(
                settings.tier_4_model
            )
            dynamic_cap = int(model_context_window * settings.tier_4_token_budget_ratio)
            return {
                "max_docs_per_session": settings.tier_4_max_docs_per_session,
                "max_document_tokens": min(
                    dynamic_cap, settings.tier_4_max_document_tokens
                ),
                "max_upload_size_bytes": settings.tier_4_max_upload_size_bytes,
                "max_files_per_request": settings.tier_4_max_files_per_request,
                "model_context_window": model_context_window,
            }

        model_context_window = self._resolve_model_context_window(settings.tier_3_model)
        dynamic_cap = int(model_context_window * settings.tier_3_token_budget_ratio)
        return {
            "max_docs_per_session": settings.tier_3_max_docs_per_session,
            "max_document_tokens": min(
                dynamic_cap, settings.tier_3_max_document_tokens
            ),
            "max_upload_size_bytes": settings.tier_3_max_upload_size_bytes,
            "max_files_per_request": settings.tier_3_max_files_per_request,
            "model_context_window": model_context_window,
        }

    def _resolve_model_context_window(self, model_name: str) -> int:
        """Resolve the context window for configured model with safe fallback."""
        normalized = (model_name or "").strip().lower()
        if normalized in MODEL_CONTEXT_WINDOWS:
            return MODEL_CONTEXT_WINDOWS[normalized]

        for known_model, context_window in MODEL_CONTEXT_WINDOWS.items():
            if known_model in normalized:
                return context_window
        return DEFAULT_MODEL_CONTEXT_WINDOW

    async def get_limits_for_tier(self, tier_id: int) -> dict[str, int]:
        """Expose limits for route-level validations."""
        return self._limits_for_tier(tier_id)

    async def _reserve_upload_quota(
        self,
        *,
        count_key: str,
        tokens_key: str,
        max_docs_per_session: int,
        max_document_tokens: int,
        estimated_tokens: int,
    ) -> dict[str, Any]:
        """Atomically reserve one document slot plus token budget in Redis."""
        payload = await self.redis_client.eval(
            UPLOAD_RESERVE_LUA,
            2,
            count_key,
            tokens_key,
            max_docs_per_session,
            max_document_tokens,
            estimated_tokens,
            settings.session_state_ttl,
        )
        allowed = int(payload[0]) == 1
        reason = str(payload[1])
        return {"allowed": allowed, "reason": reason}

    async def _rollback_reserved_quota(
        self,
        *,
        count_key: str,
        tokens_key: str,
        estimated_tokens: int,
    ) -> None:
        """Rollback reserved counters if upload fails after reservation."""
        await self.redis_client.eval(
            UPLOAD_ROLLBACK_LUA,
            2,
            count_key,
            tokens_key,
            estimated_tokens,
        )

    def _estimate_tokens(self, content: bytes, ext: str) -> int:
        """Roughly estimate the number of tokens the file will consume in the context window."""
        if ext in IMAGE_EXTENSIONS:
            return 1000  # Fixed estimate for images

        if ext in SPREADSHEET_EXTENSIONS:
            text = self._extract_spreadsheet_text(content, ext)
            return len(text) // 4 if text.strip() else len(content) // 10

        if ext == ".pdf":
            text = self._extract_document_text(content, ".pdf")
            if text.strip():
                return len(text) // 4

        # Fallback: file size estimate (e.g. Word docs)
        return len(content) // 10

    @staticmethod
    def _extract_spreadsheet_text(content: bytes, ext: str) -> str:
        """Extract text from a spreadsheet file for token estimation and inline injection."""
        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content))
            else:
                df = pd.read_excel(io.BytesIO(content))
            return df.to_string()
        except (ValueError, TypeError, OSError, ImportError) as exc:
            logger.warning(
                "Failed to extract text from spreadsheet for token estimation: %s", exc
            )
            return ""

    def _extract_document_text(self, content: bytes, ext: str) -> str:
        """Extract text from a document file for validation and estimation."""
        if ext == ".pdf":
            try:
                fitz_open = getattr(fitz, "open")
                with fitz_open(stream=content, filetype="pdf") as doc:
                    return "".join(page.get_text() for page in doc)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning("Failed to extract text from PDF: %s", exc)
        return ""

    @classmethod
    def _is_obviously_non_financial(cls, text: str) -> bool:
        """Heuristic to detect blatant non-financial/technical content.

        Checks for programming language syntax and technical keywords.
        High-precision approach: only rejects if multiple strong indicators are present.
        """
        if not text or not text.strip():
            return False

        # Technical/Code Indicators
        code_indicators = {
            "import ",
            "from ",
            "def ",
            "class ",
            "public static",
            "namespace ",
            "include <",
            "module.exports",
            "git commit",
            "kubectl ",
            "docker run",
            "apiVersion:",
            "npm install",
            "pip install",
        }

        text_lower = text.lower()

        # Check for code keywords (at least 3 unique ones)
        found_code = sum(1 for indicator in code_indicators if indicator in text_lower)
        if found_code >= 3:
            return True

        # Check for heavy programming syntax
        syntax_patterns = ["{", "}", "();", "[]", "=>", "=="]
        found_syntax = sum(1 for pattern in syntax_patterns if pattern in text)
        if (
            found_syntax >= 8
        ):  # Higher threshold for syntax to avoid false positives in tables
            return True

        # NEW: Character Density Check (Hardening)
        # Technical/Code files have a high density of syntax symbols
        density = cls._calculate_special_char_density(text)
        if density > 15.0:  # >15% special char density is a strong technical indicator
            return True

        return False

    @classmethod
    def _calculate_special_char_density(cls, text: str) -> float:
        """Calculate density of technical syntax characters in text.

        Financial text is mostly alphanumeric. Code is dense with symbols.
        """
        if not text or not text.strip():
            return 0.0

        # We count characters that are strong indicators of technical/code syntax
        technical_chars = set("{}[]();=>#<>\\")

        # Exclude whitespace from the total to get meaningful density
        non_ws_chars = [c for c in text if not c.isspace()]
        if not non_ws_chars:
            return 0.0

        tech_count = sum(1 for c in non_ws_chars if c in technical_chars)
        return (tech_count / len(non_ws_chars)) * 100
