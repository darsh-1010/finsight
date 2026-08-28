from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tier(Base):
    __tablename__ = "tiers"

    id = Column(Integer, primary_key=True, index=True)

    # Core identity
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False, unique=True, index=True)
    description = Column(String)

    # Pricing
    price_amount = Column(Integer, nullable=False)  # in paise
    price_amount_yearly = Column(Integer, nullable=True)  # in paise for yearly
    currency = Column(String, default="inr")

    # UI / catalog metadata
    highlights = Column(JSON, nullable=True)
    is_popular = Column(Boolean, default=False)

    icon = Column(String, nullable=True)

    # Relationships
    entitlements = relationship("TierEntitlement", back_populates="tier")
    subscriptions = relationship("Subscription", back_populates="tier")
    onboarding_questions_map = relationship(
        "TierOnboardingQuestion",
        back_populates="tier",
        cascade="all, delete-orphan",
        order_by="TierOnboardingQuestion.order",
    )
    token_config = relationship(
        "TierTokenConfig",
        back_populates="tier",
        uselist=False,
    )



class Entitlements(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String)
    description = Column(String)

    tiers = relationship("TierEntitlement", back_populates="entitlement")


class TierEntitlement(Base):
    __tablename__ = "tier_entitlements"

    id = Column(Integer, primary_key=True, index=True)
    tier_id = Column(Integer, ForeignKey("tiers.id"))
    entitlement_id = Column(Integer, ForeignKey("entitlements.id"))

    tier = relationship("Tier", back_populates="entitlements")
    entitlement = relationship("Entitlements", back_populates="tiers")

    def __repr__(self):
        return f"<TierEntitlement(tier_id={self.tier_id}, entitlement_id={self.entitlement_id})>"
