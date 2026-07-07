from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.models.onboarding_questioner import (
    OnboardingQuestion,
    OnboardingQuestionOption,
    TierOnboardingQuestion,
    UserOnboardingAnswer,
)
from app.models.tiers import Tier
from app.models.users import User
from app.schemas.onboarding import (
    AnswerResponse,
    AnswerUpdate,
    OnboardingQuestionResponse,
    QuestionCreate,
    QuestionUpdate,
    SimpleQuestionCreate,
)

router = APIRouter(prefix="/onboarding", tags=["Admin Onboarding"])


# -------------------------
# Create Tier Question
# -------------------------


@router.post("/tiers/{tier_id}/questions", response_model=OnboardingQuestionResponse)
def create_question(
    tier_id: int,
    question: QuestionCreate,
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    tier = db.query(Tier).filter(Tier.id == tier_id).first()
    if not tier:
        raise HTTPException(404, "Tier not found")

    question_data = question.model_dump(
        exclude={"options", "order", "depends_on_question_id", "depends_on_value"}
    )

    new_q = OnboardingQuestion(**question_data)
    db.add(new_q)
    db.flush()

    mapping = TierOnboardingQuestion(
        tier_id=tier_id,
        question_id=new_q.id,
        order=question.order,
        depends_on_question_id=question.depends_on_question_id,
        depends_on_value=question.depends_on_value,
    )
    db.add(mapping)

    if question.options:
        for opt in question.options:
            db.add(
                OnboardingQuestionOption(
                    question_id=new_q.id,
                    **opt.model_dump(),
                )
            )

    db.commit()
    db.refresh(new_q)

    # Attach tier info for response mapping
    new_q.tier_id = tier_id
    new_q.order = question.order

    return new_q


# -------------------------
# Standalone Question
# -------------------------


@router.post("/questions", response_model=OnboardingQuestionResponse)
def create_standalone_question(
    question: SimpleQuestionCreate,
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    question_data = question.model_dump(exclude={"options"})
    new_q = OnboardingQuestion(**question_data)

    db.add(new_q)
    db.flush()

    if question.options:
        for opt in question.options:
            db.add(
                OnboardingQuestionOption(
                    question_id=new_q.id,
                    **opt.model_dump(),
                )
            )

    db.commit()
    db.refresh(new_q)

    return new_q


# -------------------------
# Update Question
# -------------------------


@router.put("/questions/{question_id}", response_model=OnboardingQuestionResponse)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    question = (
        db.query(OnboardingQuestion)
        .filter(OnboardingQuestion.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(404, "Question not found")

    data = payload.model_dump(exclude_unset=True)
    options = data.pop("options", None)

    if "question_type" in data:
        used = (
            db.query(UserOnboardingAnswer)
            .filter(UserOnboardingAnswer.question_id == question.id)
            .first()
        )
        if used:
            raise HTTPException(400, "Cannot change type after answers submitted")

    mapping_fields = {"order", "depends_on_question_id", "depends_on_value"}

    for key, value in data.items():
        if key not in mapping_fields:
            setattr(question, key, value)

    if options is not None:
        (
            db.query(OnboardingQuestionOption)
            .filter(OnboardingQuestionOption.question_id == question.id)
            .delete()
        )

        for opt in options:
            db.add(
                OnboardingQuestionOption(
                    question_id=question.id,
                    **opt.model_dump(),
                )
            )

    db.commit()
    db.refresh(question)
    return question


# -------------------------
# Get All Questions
# -------------------------


@router.get("/questions", response_model=List[OnboardingQuestionResponse])
def get_all_questions(
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return db.query(OnboardingQuestion).all()


# -------------------------
# Update Tier Mapping
# -------------------------


class MappingUpdate(BaseModel):
    order: Optional[int] = None
    depends_on_question_id: Optional[int] = None
    depends_on_value: Optional[str] = None


@router.put("/tiers/{tier_id}/questions/{question_id}/mapping")
def update_tier_question_mapping(
    tier_id: int,
    question_id: int,
    payload: MappingUpdate,
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    mapping = (
        db.query(TierOnboardingQuestion)
        .filter(
            TierOnboardingQuestion.tier_id == tier_id,
            TierOnboardingQuestion.question_id == question_id,
        )
        .first()
    )

    if not mapping:
        raise HTTPException(404, "Tier-Question mapping not found")

    if payload.order is not None:
        mapping.order = payload.order
    if payload.depends_on_question_id is not None:
        mapping.depends_on_question_id = payload.depends_on_question_id
    if payload.depends_on_value is not None:
        mapping.depends_on_value = payload.depends_on_value

    db.commit()
    db.refresh(mapping)

    return {"message": "Mapping updated successfully"}


# -------------------------
# Delete Question
# -------------------------


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    _: None = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    question = (
        db.query(OnboardingQuestion)
        .filter(OnboardingQuestion.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(404, "Question not found")

    db.delete(question)
    db.commit()


# -------------------------
# User Answers
# -------------------------


@router.get("/answers", response_model=List[AnswerResponse])
def get_user_answers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(UserOnboardingAnswer)
        .filter(UserOnboardingAnswer.user_id == current_user.id)
        .all()
    )


@router.put("/answers/{answer_id}", response_model=AnswerResponse)
def update_answer(
    answer_id: int,
    payload: AnswerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    answer = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.id == answer_id,
            UserOnboardingAnswer.user_id == current_user.id,
        )
        .first()
    )

    if not answer:
        raise HTTPException(404, "Answer not found")

    answer.answer_value = payload.answer_value
    answer.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(answer)
    return answer


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    answer = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.id == answer_id,
            UserOnboardingAnswer.user_id == current_user.id,
        )
        .first()
    )

    if not answer:
        raise HTTPException(404, "Answer not found")

    db.delete(answer)
    db.commit()
