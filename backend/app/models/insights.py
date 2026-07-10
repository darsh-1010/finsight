import enum
import uuid

from sqlalchemy import (
    ARRAY,
    UUID,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class TrendType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class InsightStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class Insight(Base):
    __tablename__ = "insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    summary = Column(Text, nullable=True)
    source = Column(String, nullable=True)

    tier_required = Column(
        Integer,
        ForeignKey("tiers.id"),
        nullable=False,
    )

    # Financial / Trend Specific Fields
    ticker = Column(String, nullable=True)
    trend_type = Column(
        Enum(TrendType, name="trendtype", values_callable=_enum_values),
        nullable=True,
    )
    trend = Column(String, nullable=True)
    price_change_pct = Column(Float, nullable=True)
    key_event = Column(Text, nullable=True)
    verification_status = Column(String, nullable=True)
    citations = Column(ARRAY(String), nullable=True)
    alert_message = Column(Text, nullable=True)

    status = Column(
        Enum(InsightStatus, name="insightstatus", values_callable=_enum_values),
        default=InsightStatus.DRAFT,
        nullable=False,
    )

    published_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )

    tier = relationship("Tier")
    reviews = relationship(
        "MarketInsightReview",
        back_populates="market_insight",
        cascade="all, delete-orphan",
    )


class MarketInsightReview(Base):
    __tablename__ = "market_insight_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    market_insight_id = Column(
        UUID(as_uuid=True),
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    review_status = Column(String, nullable=False)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    market_insight = relationship("Insight", back_populates="reviews")
    reviewer = relationship("User")
