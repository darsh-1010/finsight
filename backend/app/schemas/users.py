from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    # optional tier intent
    tier_level: int | None = 1  # default = free tier


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    tier_level: int
    tier_name: str
    entitlements: list[str] = []
    is_onboarded: bool = False
    is_verified: bool = False
    experience_level: str | None = ""
    risk_level: str | None = ""
    updated_at: datetime

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class VisitingUserCreate(BaseModel):
    email: EmailStr


class VisitingUserChatCountUpdate(BaseModel):
    chat_count: int = Field(ge=0)


class VisitingUserOut(BaseModel):
    id: int
    email: EmailStr
    chat_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
