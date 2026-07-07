"""
AWS S3 utility for downloading PDF files.
"""

import os
from typing import Tuple
from urllib.parse import unquote_plus, urlparse

from config.settings import settings
from src.utils.logger import get_logger

try:
    import boto3 as BOTO3
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    BOTO3 = None

logger = get_logger(__name__)


class S3Downloader:
    """Utility class for downloading files from S3."""

    def __init__(self):
        """Initialize S3 client using project settings."""
        self.client = self._build_client()

    @staticmethod
    def _build_client():
        """Create the boto3 S3 client only when S3 download support is actually used."""
        if BOTO3 is None:
            raise RuntimeError("boto3 is required for S3 downloads")

        return BOTO3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def parse_s3_url(self, url: str) -> tuple[str, str]:
        """Parse an s3:// URL or an S3 HTTPS object URL into bucket and key components.

        Supports:
        - s3://bucket/key
        - https://bucket.s3.region.amazonaws.com/key
        - https://s3.region.amazonaws.com/bucket/key
        - https://bucket.s3.amazonaws.com/key
        """
        parsed = urlparse(url)

        if parsed.scheme == "s3":
            return parsed.netloc, unquote_plus(parsed.path.lstrip("/"))

        if parsed.scheme in ("http", "https"):
            netloc = parsed.netloc.lower()
            path = parsed.path.lstrip("/")

            # Format: bucket.s3.region.amazonaws.com or bucket.s3.amazonaws.com
            if ".s3." in netloc or ".s3-" in netloc:
                parts = netloc.split(".")
                # Find the 's3' part
                for i, part in enumerate(parts):
                    if part.startswith("s3"):
                        # Bucket is everything before 's3'
                        bucket = ".".join(parts[:i])
                        return bucket, unquote_plus(path)

            # Format: s3.region.amazonaws.com/bucket/key
            if netloc.startswith("s3.") or netloc == "s3.amazonaws.com":
                path_parts = path.split("/", 1)
                if len(path_parts) == 2:
                    return path_parts[0], unquote_plus(path_parts[1])

        # Fallback: Treat as key in default bucket if no scheme or not recognized S3 format
        bucket = settings.s3_bucket_name
        key = unquote_plus(url.lstrip("/"))
        return bucket, key

    def download_to_temp(self, s3_url: str, local_path: str) -> bool:
        """Download an S3 object to a local temporary path.

        Args:
            s3_url: The S3 URL or object key.
            local_path: Local file path to save the download.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            bucket, key = self.parse_s3_url(s3_url)
            logger.info("Downloading s3://%s/%s to %s", bucket, key, local_path)

            self.client.download_file(bucket, key, local_path)
            return os.path.getsize(local_path) > 0

        except RuntimeError as exc:
            logger.error("S3 dependency missing for %s: %s", s3_url, str(exc))
            return False
        except (ValueError, OSError) as exc:
            logger.error("Invalid path or URL for S3 download %s: %s", s3_url, str(exc))
            return False
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name in {"BotoCoreError", "ClientError"}:
                logger.error("Download failed for %s: %s", s3_url, str(exc))
                return False
            raise

    @staticmethod
    def is_s3_url(url: str) -> bool:
        """Check if a string is a valid S3 URL starting with s3://.

        Args:
            url: The string to check.

        Returns:
            bool: True if it starts with s3://.
        """
        return url.lower().startswith("s3://")
