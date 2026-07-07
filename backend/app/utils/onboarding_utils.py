from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.onboarding_questioner import (
    OnboardingQuestion,
    QuestionType,
    TierOnboardingQuestion,
    UserOnboardingAnswer,
)
from app.models.users import RiskBucket, User, UserProfile
from app.schemas.onboarding import AnswerCreate


def _coerce_choice(answer):
    """Helper for single choice/dropdown."""
    if answer is None:
        return ""
    if isinstance(answer, (int, float)):
        return str(answer)
    if not isinstance(answer, str):
        raise HTTPException(400, "Answer must be a string")
    return answer


def _coerce_multi_choice(answer):
    """Helper for multi-choice."""
    if answer is None:
        return []
    if isinstance(answer, str):
        return [answer]
    if not isinstance(answer, list):
        raise HTTPException(400, "Answer must be a list")
    return answer


def _coerce_number(answer):
    """Helper for number-type questions."""
    if answer is None:
        return 0
    if isinstance(answer, str) and answer.strip():
        try:
            return float(answer) if "." in answer else int(answer)
        except ValueError as exc:
            raise HTTPException(400, "Answer must be numeric") from exc
    if not isinstance(answer, (int, float)):
        raise HTTPException(400, "Answer must be numeric")
    return answer


def _coerce_answer_by_type(question_type: QuestionType, answer):
    """Validate and coerce answer_value based on question type."""
    if question_type in {QuestionType.SINGLE_CHOICE, QuestionType.DROPDOWN}:
        return _coerce_choice(answer)

    if question_type == QuestionType.MULTI_CHOICE:
        return _coerce_multi_choice(answer)

    if question_type == QuestionType.NUMBER:
        return _coerce_number(answer)

    return answer


def save_single_answer(db: Session, user_id: int, ans: AnswerCreate, saved_list: list):
    question = (
        db.query(OnboardingQuestion)
        .filter(OnboardingQuestion.id == ans.question_id)
        .first()
    )

    if not question:
        raise HTTPException(400, f"Question ID {ans.question_id} not found")

    # Validate & coerce answer
    ans.answer_value = _coerce_answer_by_type(question.question_type, ans.answer_value)

    existing = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.user_id == user_id,
            UserOnboardingAnswer.question_id == ans.question_id,
        )
        .first()
    )

    if existing:
        existing.answer_value = ans.answer_value
        existing.option_id = ans.option_id
        existing.updated_at = datetime.utcnow()
        saved_list.append(existing)
        return

    new = UserOnboardingAnswer(
        user_id=user_id,
        question_id=ans.question_id,
        option_id=ans.option_id,
        answer_value=ans.answer_value,
    )
    db.add(new)
    saved_list.append(new)


def check_and_update_onboarding_status(db: Session, user_id: int):
    """
    Check if all questions for the user's tier are answered.
    If yes, mark onboarding_completed in UserProfile.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.subscription:
        return

    tier_id = user.subscription.tier_id

    total_questions = (
        db.query(TierOnboardingQuestion)
        .filter(TierOnboardingQuestion.tier_id == tier_id)
        .count()
    )

    if total_questions == 0:
        if not user.profile:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
            user.profile = profile

        user.profile.onboarding_completed = True
        user.profile.updated_at = datetime.utcnow()
        db.commit()
        return

    answered_count = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.user_id == user.id,
            UserOnboardingAnswer.question_id.in_(
                db.query(TierOnboardingQuestion.question_id).filter(
                    TierOnboardingQuestion.tier_id == tier_id
                )
            ),
        )
        .count()
    )

    if answered_count >= total_questions:
        if not user.profile:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
            user.profile = profile

        user.profile.onboarding_completed = True
        user.profile.updated_at = datetime.utcnow()
        db.commit()


# ---------------- CIP Profile Calculation ---------------- #

CIP_PROFILES = {
    1: "Risk Averse",
    2: "Conservative",
    3: "Moderate",
    4: "Moderately Aggressive",
    5: "Aggressive",
    6: "Very Aggressive",
}

CIP_COMBINATION_MAP = {
    ("B", "A", "B"): 2,
    ("B", "B", "B"): 2,
    ("C", "A", "B"): 2,
    ("C", "B", "B"): 2,
    ("D", "A", "B"): 2,
    ("E", "A", "B"): 2,
    ("F", "A", "B"): 2,
    ("C", "B", "C"): 3,
    ("D", "B", "C"): 3,
    ("E", "B", "C"): 3,
    ("F", "B", "C"): 3,
    ("D", "C", "D"): 4,
    ("E", "C", "D"): 4,
    ("F", "C", "D"): 4,
    ("E", "D", "E"): 5,
    ("F", "D", "E"): 5,
    ("F", "E", "F"): 6,
}


def calculate_cip_profile_and_risk_bucket(
    q1: str, q2: str, q3: str
) -> tuple[int, RiskBucket]:
    """
    Calculate CIP profile and corresponding risk bucket.
    """
    if q3 == "A":
        return (1, RiskBucket.RISK_AVERSE)

    key = (q1, q2, q3)

    profile_to_risk_bucket = {
        1: RiskBucket.RISK_AVERSE,
        2: RiskBucket.CONSERVATIVE,
        3: RiskBucket.MODERATE,
        4: RiskBucket.MODERATELY_AGGRESSIVE,
        5: RiskBucket.AGGRESSIVE,
        6: RiskBucket.VERY_AGGRESSIVE,
    }

    profile_number = CIP_COMBINATION_MAP.get(key, 2)
    return (profile_number, profile_to_risk_bucket[profile_number])


def reverse_map_risk_bucket_to_profile(risk_bucket) -> int:
    """Convert RiskBucket back to CIP profile number."""
    reverse_mapping = {
        RiskBucket.RISK_AVERSE: 1,
        RiskBucket.CONSERVATIVE: 2,
        RiskBucket.MODERATE: 3,
        RiskBucket.MODERATELY_AGGRESSIVE: 4,
        RiskBucket.AGGRESSIVE: 5,
        RiskBucket.VERY_AGGRESSIVE: 6,
        RiskBucket.NO_RISK: 2,
    }
    return reverse_mapping.get(risk_bucket, 2)


def update_risk_bucket_from_cip(db: Session, user_id: int) -> None:
    """Update user's risk_bucket if all CIP questions are answered."""
    cip_questions = (
        db.query(OnboardingQuestion)
        .filter(OnboardingQuestion.title == "CIP Scoring")
        .order_by(OnboardingQuestion.id)
        .all()
    )

    if len(cip_questions) != 3:
        return

    user_answers = (
        db.query(UserOnboardingAnswer)
        .filter(
            UserOnboardingAnswer.user_id == user_id,
            UserOnboardingAnswer.question_id.in_([q.id for q in cip_questions]),
        )
        .all()
    )

    if len(user_answers) != 3:
        return

    answer_map = {ans.question_id: ans.answer_value for ans in user_answers}

    _, risk_bucket = calculate_cip_profile_and_risk_bucket(
        answer_map[cip_questions[0].id],
        answer_map[cip_questions[1].id],
        answer_map[cip_questions[2].id],
    )

    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    if user_profile:
        user_profile.risk_bucket = risk_bucket
        user_profile.onboarding_completed = True
        user_profile.updated_at = datetime.utcnow()
    else:
        user_profile = UserProfile(
            user_id=user_id,
            risk_bucket=risk_bucket,
            onboarding_completed=True,
            updated_at=datetime.utcnow(),
        )
        db.add(user_profile)

    db.commit()
