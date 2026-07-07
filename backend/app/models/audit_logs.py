from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    event_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    extra_metadata = Column(
        "metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    ip_address = Column(String().with_variant(INET, "postgresql"), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
