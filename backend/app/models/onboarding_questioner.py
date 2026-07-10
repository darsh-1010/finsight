import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class QuestionType(enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    DROPDOWN = "dropdown"
    FILE = "file"


class TierOnboardingQuestion(Base):
    __tablename__ = "tier_onboarding_questions"
    __table_args__ = (
        UniqueConstraint("tier_id", "question_id", name="uq_tier_question"),
        UniqueConstraint("tier_id", "order", name="uq_tier_order"),
    )
    id = Column(Integer, primary_key=True)
    tier_id = Column(Integer, ForeignKey("tiers.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("onboarding_questions.id"), nullable=False)
    order = Column(Integer, default=0)
    depends_on_question_id = Column(
        Integer, ForeignKey("onboarding_questions.id"), nullable=True
    )
    depends_on_value = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tier = relationship("Tier", back_populates="onboarding_questions_map")
    question = relationship(
        "OnboardingQuestion",
        foreign_keys=[question_id],
    )
    depends_on_question = relationship(
        "OnboardingQuestion",
        foreign_keys=[depends_on_question_id],
    )


class OnboardingQuestion(Base):
    __tablename__ = "onboarding_questions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    question_text = Column(String, nullable=False)
    question_description = Column(String, nullable=True)

    question_type = Column(
        SQLEnum(QuestionType, name="question_type_enum"), nullable=False
    )

    validation_rules = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    options = relationship(
        "OnboardingQuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="OnboardingQuestionOption.order",
    )

    answers = relationship("UserOnboardingAnswer", back_populates="question")


class OnboardingQuestionOption(Base):
    __tablename__ = "onboarding_question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("onboarding_questions.id"), nullable=False)
    label = Column(String, nullable=False)
    value = Column(String, nullable=False)
    order = Column(Integer, default=0)
    question = relationship("OnboardingQuestion", back_populates="options")
    answers = relationship("UserOnboardingAnswer", back_populates="option")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserOnboardingAnswer(Base):
    __tablename__ = "user_onboarding_answers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(
        Integer, ForeignKey("onboarding_questions.id"), nullable=False, index=True
    )
    option_id = Column(
        Integer, ForeignKey("onboarding_question_options.id"), nullable=True, index=True
    )
    answer_value = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="onboarding_answers")
    question = relationship("OnboardingQuestion", back_populates="answers")
    option = relationship("OnboardingQuestionOption", back_populates="answers")
