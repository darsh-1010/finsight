from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.onboarding_questioner import (
    OnboardingQuestion,
    TierOnboardingQuestion,
    UserOnboardingAnswer,
)
from app.models.tiers import Tier
from app.models.users import User, UserProfile
from app.schemas.onboarding import (
    AnswerCreate,
    AnswerResponse,
    CIPCalculationResponse,
)
from app.utils.onboarding_utils import (
    CIP_PROFILES,
    calculate_cip_profile_and_risk_bucket,
    check_and_update_onboarding_status,
    save_single_answer,
    update_risk_bucket_from_cip,
)

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])


@router.get("/questions")
def get_questions_by_tier(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all questions for a specific tier with proper ordering."""
    if not current_user.subscription or not current_user.subscription.tier:
        raise HTTPException(
            status_code=400, detail="User has no active subscription tier"
        )

    tier_id = current_user.subscription.tier.id
    tier = db.query(Tier).filter(Tier.id == tier_id).first()

    if not tier:
        raise HTTPException(status_code=404, detail="Tier not found")

    mappings = (
        db.query(TierOnboardingQuestion)
        .filter(TierOnboardingQuestion.tier_id == tier_id)
        .order_by(TierOnboardingQuestion.order)
        .all()
    )

    # Build response with question data and order from mapping
    result = []
    for mapping in mappings:
        question = mapping.question
        result.append(
            {
                "id": question.id,
                "question_text": question.question_text,
                "question_description": question.question_description,
                "title": question.title,
                "question_type": question.question_type,
                "order": mapping.order,
                "validation_rules": question.validation_rules,
                "options": [
                    {
                        "id": opt.id,
                        "label": opt.label,
                        "value": opt.value,
                        "order": opt.order,
                    }
                    for opt in question.options
                ],
            }
        )

    return result


@router.post("/answers", response_model=list[AnswerResponse])
def submit_answers(
    answers: list[AnswerCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved_answers = []
    for ans in answers:
        save_single_answer(db, current_user.id, ans, saved_answers)

    db.commit()
    for ans in saved_answers:
        db.refresh(ans)

    # Check if CIP questions are answered and update risk_bucket
    update_risk_bucket_from_cip(db, current_user.id)

    # Check if onboarding is completed
    check_and_update_onboarding_status(db, current_user.id)

    return saved_answers


@router.post("/answer", response_model=AnswerResponse)
def submit_single_answer(
    answer: AnswerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = []
    save_single_answer(db, current_user.id, answer, saved)

    db.commit()
    db.refresh(saved[0])

    # Check if onboarding is completed after single answer
    check_and_update_onboarding_status(db, current_user.id)

    return saved[0]


@router.get("/calculate-cip-profile", response_model=CIPCalculationResponse)
def calculate_cip_profile_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Calculate CIP (Customer Investment Profile) based on user's answers.
    Compares with existing profile and updates only if different.
    """

    # Get user profile
    user_profile = (
        db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    )

    # Get CIP questions
    cip_questions = (
        db.query(OnboardingQuestion)
        .filter(OnboardingQuestion.title == "CIP Scoring")
        .order_by(OnboardingQuestion.id)
        .all()
    )

    if len(cip_questions) != 3:
        raise HTTPException(
            status_code=500,
            detail=f"Expected 3 CIP questions, found {len(cip_questions)}. Please ensure CIP questions are seeded.",
        )

    # Get user's answers for these questions
    user_answers = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.user_id == current_user.id,
            UserOnboardingAnswer.question_id.in_([q.id for q in cip_questions]),
        )
        .all()
    )

    # Create a mapping of question_id to answer_value
    answer_map = {ans.question_id: ans.answer_value for ans in user_answers}

    # Check if all three answers exist
    missing_questions = [q.id for q in cip_questions if q.id not in answer_map]
    if missing_questions:
        raise HTTPException(
            status_code=400,
            detail="Missing answers for CIP questions. Please answer all three CIP questions first.",
        )

    # Extract answer values in order (q1, q2, q3)
    q1_answer = answer_map[cip_questions[0].id]
    q2_answer = answer_map[cip_questions[1].id]
    q3_answer = answer_map[cip_questions[2].id]

    # Always calculate profile from current answers
    calculated_profile_number, calculated_risk_bucket = (
        calculate_cip_profile_and_risk_bucket(q1_answer, q2_answer, q3_answer)
    )

    # Check if we need to update the profile
    profile_updated = False

    if user_profile:
        # Compare calculated risk bucket with existing profile
        if user_profile.risk_bucket != calculated_risk_bucket:
            # Update profile since it's different
            user_profile.risk_bucket = calculated_risk_bucket
            user_profile.onboarding_completed = True
            user_profile.updated_at = datetime.utcnow()
            profile_updated = True
            db.commit()
            db.refresh(user_profile)
    else:
        # Create new profile if it doesn't exist
        user_profile = UserProfile(
            user_id=current_user.id,
            risk_bucket=calculated_risk_bucket,
            onboarding_completed=True,
            updated_at=datetime.utcnow(),
        )
        db.add(user_profile)
        profile_updated = True
        db.commit()
        db.refresh(user_profile)

    return {
        "profile_number": calculated_profile_number,
        "profile_name": CIP_PROFILES[calculated_profile_number],
        "q1_answer": q1_answer,
        "q2_answer": q2_answer,
        "q3_answer": q3_answer,
        "updated": profile_updated,
        "message": "Profile updated successfully"
        if profile_updated
        else "No changes needed, profile is up to date",
    }
