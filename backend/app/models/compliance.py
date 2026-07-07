import enum
from datetime import datetime

from sqlalchemy import (func, 
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    Enum,
    DateTime,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DisclosureType(str, enum.Enum):
    RISK = "risk"
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"


class ComplianceGroup(Base):
    __tablename__ = "compliance_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    key = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    disclosures = relationship(
        "ComplianceDisclosure",
        back_populates="group",
        order_by="ComplianceDisclosure.sort_order",
    )


class ComplianceDisclosure(Base):
    __tablename__ = "compliance_disclosures"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer,
        ForeignKey("compliance_groups.id"),
        nullable=False,
    )

    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    disclosure_type = Column(
        Enum(DisclosureType, name="disclosuretype"),
        default=DisclosureType.INFO,
        nullable=False,
    )

    icon_name = Column(String, nullable=False)  # e.g., "RiAlertFill"
    color = Column(String, nullable=True)  # e.g., "text-red-500" or hex
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    group = relationship(
        "ComplianceGroup",
        back_populates="disclosures",
    )
