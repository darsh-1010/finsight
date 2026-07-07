from sqlalchemy.orm import Session
from app.core.database import SESSION_LOCAL
from app.models.tiers import Tier
from app.models.onboarding_questioner import (
    OnboardingQuestion,
    OnboardingQuestionOption,
    TierOnboardingQuestion,
    QuestionType,
    UserOnboardingAnswer,
)
from app.models.users import UserProfile, RiskBucket

# Common CIP Scoring Questions (shared across all tiers)
COMMON_CIP_QUESTIONS = [
    {
        "title": "CIP Scoring",
        "question_text": "What is the maximum percentage (%) of your investments "
                         "that you can afford to lose in the next 12 months?",
        "question_description": "Affordability refers to the % you could lose "
                                "without impacting your current standard of living [cite: 116]",
        "question_type": QuestionType.SINGLE_CHOICE,
        "options": [
            {"label": "Less than 1%", "value": "A", "order": 0},
            {"label": "1-10%", "value": "B", "order": 1},
            {"label": ">10-15%", "value": "C", "order": 2},
            {"label": ">15-20%", "value": "D", "order": 3},
            {"label": ">20-30%", "value": "E", "order": 4},
            {"label": "Over 30%", "value": "F", "order": 5},
        ],
    },
    {
        "title": "CIP Scoring",
        "question_text": "Will you need to be able to access the cash value of your investments?",
        "question_description": "Financial Situation assessment for liquidity needs [cite: 119]",
        "question_type": QuestionType.SINGLE_CHOICE,
        "options": [
            {"label": "I may need to withdraw 75%", "value": "A", "order": 0},
            {"label": "I may need to withdraw 50%", "value": "B", "order": 1},
            {"label": "I may need to withdraw 25%", "value": "C", "order": 2},
            {"label": "I may need to withdraw 10%", "value": "D", "order": 3},
            {"label": "I do not need to withdraw", "value": "E", "order": 4},
        ],
    },
    {
        "title": "CIP Scoring",
        "question_text": "What is your investment objective and risk attitude?",
        "question_description": "Risk Situation and primary investment goal [cite: 133]",
        "question_type": QuestionType.SINGLE_CHOICE,
        "options": [
            {"label": "Protect capital; no risk", "value": "A", "order": 0},
            {"label": "Low risk; returns above deposits", "value": "B", "order": 1},
            {"label": "Moderate growth; mod risk", "value": "C", "order": 2},
            {"label": "Mod-High growth; risk", "value": "D", "order": 3},
            {"label": "High growth; significant risk", "value": "E", "order": 4},
            {"label": "Very High growth; extreme risk", "value": "F", "order": 5},
        ],
    },
]

# Tier-specific questions
TIER_SPECIFIC_QUESTIONS = {
    1: [  # Foundation tier
        {
            "title": "Education level",
            "question_text": "What is your highest level of education?",
            "question_description": "Investment Knowledge and Experience",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "Primary or lower", "value": "A", "order": 0},
                {"label": "Secondary", "value": "B", "order": 1},
                {"label": "Diploma or higher", "value": "C", "order": 2},
            ],
        },
        {
            "title": "Investment objective",
            "question_text": "What is the longest period of time you would hold an investment in your portfolio?",
            "question_description": "Analysis time horizon assessment",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "Up to 1 year", "value": "A", "order": 0},
                {"label": ">1-3 years", "value": "B", "order": 1},
                {"label": ">3-5 years", "value": "C", "order": 2},
                {"label": "Over 5 years", "value": "D", "order": 3},
            ],
        },
    ],
    2: [  # Tier 2
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have knowledge/experience in Shares and standard ETFs?",
            "question_description": "Investor level readiness for equity markets",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you understand how Mutual Funds work?",
            "question_description": "Investor level readiness for collective investment schemes",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have knowledge about Government or Corporate Bonds",
            "question_description": "Understanding of Debt Securities",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
    ],
    3: [  # Tier 3
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have knowledge of Precious Metals, Oil, or Base Metals?",
            "question_description": "Knowledge about COMMODITIES for Portfolio tier [cite: 104]",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have knowledge of Vanilla Structured Products (Premium Deposits)?",
            "question_description": "Intermediate level structured products [cite: 104]",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have experience with Hedge Funds or Alternative Mutual Funds?",
            "question_description": "Knowledge about alternatives for portfolio diversification",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
    ],
    4: [  # Tier 4
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you understand Complex ETFs (Inverse, Leveraged, or REIT ETFs)?",
            "question_description": "Advanced knowledge for FinSight Pro signals",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Are you familiar with Equity-Linked Notes or Booster/Digital Notes?",
            "question_description": "Non-vanilla structured product knowledge [cite: 104]",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you hold professional qualifications (CFA, CFP, etc.)?",
            "question_description": "Assessing professional background [cite: 93]",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
    ],
    5: [  # Tier 5
        {
            "title": "Investment Knowledge and Experience",
            "question_text": "Do you have experience with Forwards, Swaps, or Contract-Based Derivatives?",
            "question_description": "Professional derivative experience for Elite advisory",
            "question_type": QuestionType.SINGLE_CHOICE,
            "options": [
                {"label": "yes", "value": "yes", "order": 0},
                {"label": "no", "value": "no", "order": 1},
            ],
        },
    ],
}


def clear_existing_data(db: Session):
    """Clear all existing onboarding questions, options, answers, and reset onboarding status."""
    print("🧹 Clearing existing onboarding data...")

    # 1. Delete all user onboarding answers
    answer_count = db.query(UserOnboardingAnswer).delete()
    print(f" ✓ Deleted {answer_count} user answers")

    # 2. Reset onboarding_completed flag and risk_bucket for all user profiles
    profile_count = db.query(UserProfile).update(
        {
            UserProfile.onboarding_completed: False,
            UserProfile.risk_bucket: RiskBucket.NO_RISK,
        }
    )
    print(
        f" ✓ Reset onboarding status and risk bucket for {profile_count} user profiles"
    )

    # 3. Delete tier-question links
    tier_link_count = db.query(TierOnboardingQuestion).delete()
    print(f" ✓ Deleted {tier_link_count} tier-question links")

    # 4. Delete all question options
    option_count = db.query(OnboardingQuestionOption).delete()
    print(f" ✓ Deleted {option_count} question options")

    # 5. Delete all questions
    question_count = db.query(OnboardingQuestion).delete()
    print(f" ✓ Deleted {question_count} questions")

    db.flush()
    print("   ✅ All existing data cleared successfully")


def create_question(db: Session, q_data: dict) -> OnboardingQuestion:
    """Create a new question with its options."""
    # Create the question
    question = OnboardingQuestion(
        title=q_data["title"],
        question_text=q_data["question_text"],
        question_description=q_data["question_description"],
        question_type=q_data["question_type"],
    )
    db.add(question)
    db.flush()  # Flush to get question ID

    # Create options
    if q_data.get("options"):
        for opt_data in q_data["options"]:
            new_opt = OnboardingQuestionOption(
                question_id=question.id,
                label=opt_data["label"],
                value=opt_data["value"],
                order=opt_data["order"],
            )
            db.add(new_opt)

    return question


def link_question_to_tier(
    db: Session, tier: Tier, question: OnboardingQuestion, order: int
):
    """Link a question to a tier with a specific order."""
    # Create new tier-question link
    tier_question_link = TierOnboardingQuestion(
        tier_id=tier.id,
        question_id=question.id,
        order=order,
    )
    db.add(tier_question_link)
    db.flush()


def seed_cip_questions():
    db: Session = SESSION_LOCAL()
    try:
        print("🌱 Seeding CIP Scoring and Investment Knowledge Questions...")

        # Clear all existing data first
        clear_existing_data(db)

        # Get all tiers
        all_tiers = db.query(Tier).order_by(Tier.level).all()
        if not all_tiers:
            print("   ❌ No tiers found. Please seed tiers first.")
            return

        print(f"   Found {len(all_tiers)} tiers")

        # Create all common CIP questions (fresh insert)
        common_questions = []
        for q_data in COMMON_CIP_QUESTIONS:
            print(f"   ➕ Creating Common Question: {q_data['question_text'][:60]}...")
            question = create_question(db, q_data)
            common_questions.append(question)

        # Map common questions to ALL tiers (starting from order 0)
        for tier in all_tiers:
            print(
                f"   🔗 Mapping common questions to Tier {tier.level} ({tier.name})..."
            )
            for idx, question in enumerate(common_questions):
                link_question_to_tier(db, tier, question, order=idx)

        # Now process tier-specific questions
        for tier in all_tiers:
            tier_level = tier.level
            if tier_level not in TIER_SPECIFIC_QUESTIONS:
                print(f"   ⏭️  No tier-specific questions for Tier {tier_level}")
                continue

            print(f"   📝 Processing Tier {tier_level} specific questions...")
            # Start order after common questions (3 common questions = orders 0, 1, 2)
            start_order = len(common_questions)

            for idx, q_data in enumerate(TIER_SPECIFIC_QUESTIONS[tier_level]):
                question = create_question(db, q_data)
                link_question_to_tier(db, tier, question, order=start_order + idx)

        db.commit()
        print("✅ CIP questions seeded successfully.")

    except Exception as e:
        print(f"❌ Error seeding CIP questions: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_cip_questions()
