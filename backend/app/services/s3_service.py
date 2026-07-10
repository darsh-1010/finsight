import logging
import mimetypes

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    async def upload_file(self, file: UploadFile, object_name: str = None) -> str:
        """
        Uploads a file to an S3 bucket and returns the file URL.
        """
        if object_name is None:
            object_name = file.filename

        content_type = file.content_type
        if not content_type:
            content_type = (
                mimetypes.guess_type(object_name)[0] or "application/octet-stream"
            )

        try:
            self.s3_client.upload_fileobj(
                file.file,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": content_type},
            )

            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{object_name}"
            return url

        except ClientError as e:
            logger.error("S3 upload error: %s", e)

            raise HTTPException(
                status_code=500,
                detail="Failed to upload file to S3",
            ) from e

    async def upload_fileobj(
        self, fileobj, object_name: str, content_type: str = None
    ) -> str:
        """
        Uploads a file-like object to an S3 bucket and returns the file URL.
        """
        if not content_type:
            content_type = (
                mimetypes.guess_type(object_name)[0] or "application/octet-stream"
            )

        try:
            self.s3_client.upload_fileobj(
                fileobj,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": content_type},
            )

            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{object_name}"
            return url

        except ClientError as e:
            logger.error("S3 upload error: %s", e)

            raise HTTPException(
                status_code=500,
                detail="Failed to upload file-like object to S3",
            ) from e

    async def get_presigned_url(
        self,
        object_name: str,
        expiration: int = settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
        content_type: str = None,
        inline: bool = True,
    ) -> str:
        """
        Generate a presigned URL to share an S3 object.
        """
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": object_name,
            }

            if not content_type:
                content_type = mimetypes.guess_type(object_name)[0]

            if content_type:
                params["ResponseContentType"] = content_type

            if inline:
                params["ResponseContentDisposition"] = "inline"
            else:
                params["ResponseContentDisposition"] = "attachment"

            response = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
            )
            return response

        except ClientError as e:
            logger.error("S3 presigned URL error: %s", e)

            raise HTTPException(
                status_code=500,
                detail="Failed to generate presigned URL",
            ) from e

    async def delete_file(self, object_name: str) -> bool:
        """
        Deletes a file from an S3 bucket.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True

        except ClientError as e:
            logger.error("S3 deletion error: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to delete file from S3",
            ) from e


s3_service = S3Service()
