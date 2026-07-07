import uuid

from sqlalchemy import (func, 
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
    Text,
    UUID,
    text,
    BigInteger,
    JSON,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(
        Date,
        server_default=text("CURRENT_DATE"),
        nullable=False,
    )

    messages_used = Column(Integer, default=0, nullable=False)

    user = relationship(
        "User",
        back_populates="usage_counters",
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    session_id = Column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    started_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    title = Column(String, nullable=True)
    model = Column(String, default="standard", nullable=False)

    user = relationship(
        "User",
        back_populates="chat_sessions",
    )

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by=(
            "ChatMessage.created_at, "
            "ChatMessage.role.desc()"
        ),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id"),
        nullable=False,
    )

    role = Column(String, nullable=False)  # 'user' or 'bot'
    content = Column(Text, nullable=False)
    non_substantive = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    session = relationship(
        "ChatSession",
        back_populates="messages",
    )

    has_attachments = Column(Boolean, default=False, nullable=False)
    message_attachment_links = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
    attachments = relationship("Attachment", secondary="message_attachments", viewonly=True)


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50))         # pdf, image, docx
    file_size = Column(BigInteger)
    storage_url = Column(Text)              # S3/GCS URL
    storage_provider = Column(String(50))  # s3, gcs
    checksum = Column(String(255))         # for deduplication
    status = Column(String(50))            # uploaded, processing, ready, failed
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="attachments")
    messages = relationship("MessageAttachment", back_populates="attachment", cascade="all, delete-orphan")


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(BigInteger, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    attachment_id = Column(UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    message = relationship("ChatMessage", back_populates="message_attachment_links")
    attachment = relationship("Attachment", back_populates="messages")
