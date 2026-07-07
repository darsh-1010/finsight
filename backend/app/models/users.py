import enum
from datetime import datetime

from sqlalchemy import (func, 
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ---------------- ENUMS ---------------- #

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ExperienceLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class RiskBucket(str, enum.Enum):
    NO_RISK = "no_risk"
    RISK_AVERSE = "risk_averse"
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    MODERATELY_AGGRESSIVE = "moderately_aggressive"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


# Helper to force .value usage everywhere
def enum_values(enum_cls):
    return [e.value for e in enum_cls]


# ---------------- MODELS ---------------- #

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)

    role = Column(
        Enum(
            UserRole,
            name="userrole",
            values_callable=enum_values,
        ),
        unique=True,
        nullable=False,
    )

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    status = Column(
        Enum(
            UserStatus,
            name="userstatus",
            values_callable=enum_values,
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    role_id = Column(Integer, ForeignKey("roles.id"))

    role = relationship("Role", back_populates="users")
    sessions = relationship("UserSession", back_populates="user")
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    subscription = relationship("Subscription", back_populates="user", uselist=False)

    onboarding_answers = relationship("UserOnboardingAnswer", back_populates="user")
    usage_counters = relationship("UsageCounter", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    ingested_pdfs = relationship("IngestedPDF", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("UserVerificationToken", back_populates="user", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="user", cascade="all, delete-orphan")
    token_wallet = relationship(
        "UserTokenWallets",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    daily_token_usage = relationship(
        "DailyTokenUsage",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    token_transactions = relationship(
        "TokenTransactions",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    token_hash = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    experience_level = Column(
        Enum(
            ExperienceLevel,
            name="experiencelevel",
            values_callable=enum_values,
        ),
        default=ExperienceLevel.BEGINNER,
        nullable=False,
    )

    risk_bucket = Column(
        Enum(
            RiskBucket,
            name="riskbucket",
            values_callable=enum_values,
        ),
        default=RiskBucket.NO_RISK,
        nullable=False,
    )

    onboarding_completed = Column(Boolean, default=False)
    updated_at = Column(DateTime)

    user = relationship("User", back_populates="profile")


class UserVerificationToken(Base):
    __tablename__ = "user_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    token_type = Column(String, nullable=False)  # "verification" or "password_reset"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="verification_tokens")


class VisitingUser(Base):
    __tablename__ = "visiting_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    chat_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

