import enum
from sqlalchemy import (
    func,
    Column,
    BigInteger,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class NotificationPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AudienceType(str, enum.Enum):
    ALL = "all"
    TIER = "tier"
    USER = "user"
    ADMIN = "admin"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    notification_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    
    priority = Column(
        Enum(NotificationPriority, name="notificationpriority"),
        default=NotificationPriority.MEDIUM,
        nullable=False,
    )
    
    action_url = Column(String, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    audiences = relationship("NotificationAudience", back_populates="notification", cascade="all, delete-orphan")
    reads = relationship("UserNotificationRead", back_populates="notification", cascade="all, delete-orphan")


class NotificationAudience(Base):
    __tablename__ = "notification_audience"

    id = Column(BigInteger, primary_key=True, index=True)
    notification_id = Column(
        BigInteger,
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    audience_type = Column(
        Enum(AudienceType, name="audiencetype"),
        nullable=False,
    )
    
    audience_id = Column(String, nullable=True)

    notification = relationship("Notification", back_populates="audiences")


class UserNotificationRead(Base):
    __tablename__ = "user_notification_reads"

    id = Column(BigInteger, primary_key=True)

    notification_id = Column(
        BigInteger,
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    is_read = Column(
        Boolean,
        nullable=False,
        default=False
    )

    read_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    notification = relationship("Notification", back_populates="reads")

    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_notification_user_read"
        ),
    )
