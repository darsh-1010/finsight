from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.models.onboarding_questioner import QuestionType


class OnboardingQuestionOptionResponse(BaseModel):
    id: int
    label: str
    value: str
    order: int

    model_config = {"from_attributes": True}


class OnboardingQuestionResponse(BaseModel):
    id: int
    tier_id: int | None = None
    question_text: str
    question_description: str | None = None
    title: str | None = None
    question_type: QuestionType
    order: int | None = None
    validation_rules: Any | None = None
    options: list[OnboardingQuestionOptionResponse] = []

    model_config = {"from_attributes": True}


class AnswerCreate(BaseModel):
    question_id: int
    option_id: int | None = None
    answer_value: Any


class AnswerUpdate(BaseModel):
    answer_value: Any
    option_id: int | None = None


class AnswerResponse(BaseModel):
    id: int
    question_id: int
    option_id: int | None = None
    answer_value: Any

    model_config = {"from_attributes": True}


# --- Admin Schemas ---


class QuestionOptionCreate(BaseModel):
    label: str
    value: str
    order: int = 0


class BaseQuestionCreate(BaseModel):
    tier_id: int
    question_text: str
    question_description: str | None = None
    title: str | None = None
    order: int = 0
    validation_rules: dict | None = None
    depends_on_question_id: int | None = None
    depends_on_value: str | None = None


class TextQuestionCreate(BaseQuestionCreate):
    question_type: Literal["text"]


class NumberQuestionCreate(BaseQuestionCreate):
    question_type: Literal["number"]


class EmailQuestionCreate(BaseQuestionCreate):
    question_type: Literal["email"]


class PhoneQuestionCreate(BaseQuestionCreate):
    question_type: Literal["phone"]


class DateQuestionCreate(BaseQuestionCreate):
    question_type: Literal["date"]


class FileQuestionCreate(BaseQuestionCreate):
    question_type: Literal["file"]


class ChoiceQuestionCreate(BaseQuestionCreate):
    question_type: Literal["single_choice", "multi_choice", "dropdown"]
    options: list[QuestionOptionCreate]

    @field_validator("options")
    @classmethod
    def validate_options(cls, v):
        if not v:
            raise ValueError("Options are required for choice questions")
        return v


QuestionCreate = Annotated[
    Union[
        TextQuestionCreate,
        NumberQuestionCreate,
        EmailQuestionCreate,
        PhoneQuestionCreate,
        DateQuestionCreate,
        FileQuestionCreate,
        ChoiceQuestionCreate,
    ],
    Field(discriminator="question_type"),
]


class QuestionUpdate(BaseModel):
    question_text: str | None = None
    question_description: str | None = None
    title: str | None = None
    question_type: QuestionType | None = None
    order: int | None = None
    validation_rules: Any | None = None
    options: list[QuestionOptionCreate] | None = None
    depends_on_question_id: int | None = None
    depends_on_value: str | None = None


class SimpleQuestionCreate(BaseModel):
    """Schema for creating a standalone question without tier association"""

    question_text: str
    question_description: str | None = None
    title: str | None = None
    question_type: QuestionType
    validation_rules: dict | None = None
    options: list[QuestionOptionCreate] | None = None


class CIPCalculationResponse(BaseModel):
    """Response schema for CIP profile calculation"""

    profile_number: int = Field(..., description="Profile number (1-6)")
    profile_name: str = Field(..., description="Profile name")
    q1_answer: str = Field(..., description="Answer to question 1")
    q2_answer: str = Field(..., description="Answer to question 2")
    q3_answer: str = Field(..., description="Answer to question 3")
    updated: bool = Field(..., description="Whether the profile was updated")
    message: str = Field(..., description="Status message")
    message: str = Field(..., description="Status message")
