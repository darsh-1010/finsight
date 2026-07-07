import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class SESService:
    def __init__(self):
        self.ses_client = boto3.client(
            "ses",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.SES_REGION_NAME or settings.AWS_REGION,
        )
        self.sender_email = settings.SES_SENDER_EMAIL

    def send_email(self, to_email: str, subject: str, html_content: str):
        """
        Sends an email using AWS SES.
        """
        if not self.sender_email:
            print(f"SES_SENDER_EMAIL not configured. Email to {to_email} not sent.")
            logger.warning(
                "SES_SENDER_EMAIL not configured. Email to %s not sent.", to_email
            )
            return False

        print(f"Attempting to send email to {to_email} from {self.sender_email}...")

        try:
            response = self.ses_client.send_email(
                Source=f'"FinSight - Education-First AI Investment Intelligence Platform" <{self.sender_email}>',
                Destination={
                    "ToAddresses": [to_email],
                },
                Message={
                    "Subject": {
                        "Data": subject,
                    },
                    "Body": {
                        "Html": {
                            "Data": html_content,
                        },
                    },
                },
            )
            print(f"Email sent to {to_email}. Message ID: {response['MessageId']}")
            logger.info(
                "Email sent to %s. Message ID: %s", to_email, response["MessageId"]
            )
            return True
        except ClientError as e:
            print(f"SES send email error: {e}")
            logger.error("SES send email error: %s", e)
            return False

    def send_verification_email(
        self,
        user_email: str,
        token: str,
        tier_name: str = "Foundation",
        tier_features: list[str] = None,
    ):
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        subject = "Welcome to FinSight! Please verify your email"

        if not tier_features:
            tier_features = ["Access to basic features", "Community support"]

        features_html = "".join([f"<li>{feature}</li>" for feature in tier_features])

        template_path = (
            Path(__file__).parent.parent / "templates" / "email" / "verification.html"
        )
        with open(template_path, encoding="utf-8") as f:
            html_content = f.read()
            html_content = html_content.replace(
                "{verification_link}", verification_link
            )
            html_content = html_content.replace("{tier_name}", tier_name)
            html_content = html_content.replace("{tier_features_html}", features_html)

        return self.send_email(user_email, subject, html_content)

    def send_password_reset_email(self, user_email: str, token: str):
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Reset your FinSight password"

        template_path = (
            Path(__file__).parent.parent / "templates" / "email" / "password_reset.html"
        )
        with open(template_path, encoding="utf-8") as f:
            html_content = f.read().replace("{reset_link}", reset_link)

        return self.send_email(user_email, subject, html_content)


ses_service = SESService()
