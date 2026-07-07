import enum

from sqlalchemy import (func, 
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class SignalType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String, nullable=False)

    signal_type = Column(
        Enum(SignalType),
        nullable=False,
    )

    explanation = Column(Text, nullable=True)

    tier_required = Column(
        Integer,
        ForeignKey("tiers.id"),
        nullable=False,
    )

    status = Column(
        Enum(SignalStatus),
        default=SignalStatus.ACTIVE,
    )

    approved = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    tier = relationship("Tier")
