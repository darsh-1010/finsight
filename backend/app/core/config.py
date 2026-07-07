import json
from typing import Any, Dict, Optional

from pydantic import PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Backend"

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str | None = None

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    BACKEND_CORS_ORIGINS: list[str] = []

    ML_API_URL: str = "http://localhost:8000"
    ML_SERVER_SECRET_TOKEN: str = (
        "0eW2d8E9L18opApMBYjUV6965Cjs59Ri1QxKHxL7MpSfHtmCtYVuvgzek6xzd4Oa"
    )

    @validator(
        "ML_API_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "S3_BUCKET_NAME",
        pre=True,
    )
    @classmethod
    def clean_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip(" \"'")
        return v

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    @classmethod
    def assemble_cors_origins(
        cls,
        v: str | list[str],
    ) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]

        if isinstance(v, str):
            return json.loads(v)

        if isinstance(v, list):
            return v

        raise ValueError(v)

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 604800  # Default to 7 days (max allowed)

    SES_SENDER_EMAIL: str = ""
    SES_REGION_NAME: str | None = None
    FRONTEND_URL: str = "http://localhost:3000"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    CRON_INTERVAL_SECONDS: int = 600
    CRON_RUN_ON_START: bool = True
    CRON_INSIGHTS_SYNC_HOUR_IST: int = 6
    CRON_INSIGHTS_SYNC_MINUTE_IST: int = 0
    CRON_WEEKLY_INSIGHTS_SYNC_DAY: int = 5

    @validator("DATABASE_URL", pre=True)
    @classmethod
    def assemble_db_connection(
        cls,
        v: str | None,
        values: dict[str, Any],
    ) -> str:
        if isinstance(v, str):
            return v

        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=values.get("POSTGRES_USER"),
                password=values.get("POSTGRES_PASSWORD"),
                host=values.get("POSTGRES_SERVER"),
                port=int(values.get("POSTGRES_PORT") or 5432),
                path=f"{values.get('POSTGRES_DB') or ''}",
            )
        )

    class Config:
        case_sensitive = True
        env_file = (".env", "../.env", "../../.env")
        extra = "ignore"


settings = Settings()
