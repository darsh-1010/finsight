import asyncio
import unittest
from unittest.mock import MagicMock, patch

from app.services.s3_service import S3Service


class TestS3Service(unittest.TestCase):
    @patch("boto3.client")
    def test_s3_service_logic(self, mock_boto_client):
        """
        Since we need to run async methods, we use a single entry point
        to manage the event loop for multiple tests.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Setup mock client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        service = S3Service()

        # 1. Test Upload
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.file = MagicMock()

        upload_url = loop.run_until_complete(service.upload_file(mock_file))
        mock_s3.upload_fileobj.assert_called_once()
        self.assertIn("test.txt", upload_url)

        # 2. Test Presigned URL
        mock_s3.generate_presigned_url.return_value = (
            "https://presigned-url.com/test.txt"
        )
        presigned_url = loop.run_until_complete(service.get_presigned_url("test.txt"))

        from app.core.config import settings

        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": service.bucket_name,
                "Key": "test.txt",
                "ResponseContentType": "text/plain",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
        )
        self.assertEqual(presigned_url, "https://presigned-url.com/test.txt")

        loop.close()


if __name__ == "__main__":
    unittest.main()
