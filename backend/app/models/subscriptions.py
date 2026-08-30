import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.core.database import Base

# ---------------- ENUMS ---------------- #


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    TRAILING = "trailing"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PENDING_PAYMENT = "pending_payment"


class SubscriptionSource(enum.StrEnum):
    FREE = "free"
    STRIPE = "stripe"
    ADMIN = "admin"


class ChangeType(enum.StrEnum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    SIGNUP = "signup"
    EXPIRE = "expire"


class ChangeSource(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


# Helper to force .value usage
def enum_values(enum_cls):
    return [e.value for e in enum_cls]


# ---------------- MODELS ---------------- #


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
    )

    tier_id = Column(
        Integer,
        ForeignKey("tiers.id"),
    )

    status = Column(
        Enum(
            SubscriptionStatus,
            name="subscriptionstatus",
            values_callable=enum_values,
        ),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )

    source = Column(
        Enum(
            SubscriptionSource,
            name="subscriptionsource",
            values_callable=enum_values,
        ),
        default=SubscriptionSource.FREE,
        nullable=False,
    )

    started_at = Column(
        DateTime,
        server_default=func.now(),
    )

    ends_at = Column(DateTime)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    pending_tier_id = Column(Integer, nullable=True)
    pending_started_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="subscription")
    tier = relationship("Tier", back_populates="subscriptions")


class SubscriptionChange(Base):
    __tablename__ = "subscription_changes"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    previous_tier_id = Column(Integer)
    new_tier_id = Column(Integer)

    change_type = Column(
        Enum(
            ChangeType,
            name="changetype",
            values_callable=enum_values,
        ),
        nullable=False,
    )

    source = Column(
        Enum(
            ChangeSource,
            name="changesource",
            values_callable=enum_values,
        ),
        nullable=False,
    )

    effective_from = Column(DateTime)
    effective_to = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )
