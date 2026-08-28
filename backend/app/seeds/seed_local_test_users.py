import os
import sys

# Set database URL environment variable
if "POSTGRES_SERVER" not in os.environ and "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
sys.path.append("backend")

from app.core.database import SESSION_LOCAL, Base, engine
from app.core.security import hash_password
from app.models.subscriptions import (
    Subscription,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.tiers import Entitlements, Tier, TierEntitlement
from app.models.users import Role, User, UserRole, UserStatus

# Entitlements
ENTITLEMENTS = [
    ("CHAT_ACCESS_BASIC", "Basic chat access"),
    ("CHAT_ACCESS_EXTENDED", "Extended chat with memory"),
    ("CHAT_ACCESS_PRIORITY", "Priority chat responses"),
    ("MEMORY_NONE", "No conversation memory"),
    ("MEMORY_SHORT", "Session-based memory"),
    ("MEMORY_LONG", "Long-term memory"),
    ("INSIGHTS_NONE", "No insights"),
    ("INSIGHTS_BASIC", "Basic educational insights"),
    ("INSIGHTS_PORTFOLIO", "Portfolio & macro insights"),
    ("INSIGHTS_PRO", "AI-powered insights"),
    ("SIGNALS_NONE", "No signals"),
    ("SIGNALS_EDUCATIONAL", "Illustrative signals"),
    ("SIGNALS_AI", "AI-detected patterns"),
    ("BRIEFINGS_WEEKLY", "Weekly intelligence briefings"),
    ("ADVISORY_DISABLED", "No advisory access"),
    ("ADVISORY_INTAKE", "Advisory intake & explanation"),
    ("ADVISORY_HUMAN", "Human advisor access"),
]

# Tiers
TIER_CATALOG = [
    {
        "level": 1,
        "name": "Starter",
        "description": "Start Understanding how investing really works.",
        "price_amount": 0,
        "highlights": [
            "8-10 foundational lessons (basics of investing)",
            "Worksheets and learning frameworks",
            "FinSight in read-only / explain mode",
            "Core concepts explained clearly",
            "No asset-specific guidance",
        ],
        "icon": "book",
    },
    {
        "level": 2,
        "name": "Growth",
        "description": "Build the mindset professionals use.",
        "price_amount": 2900,
        "highlights": [
            "Full Build Your Wealth curriculum",
            "Investor psychology & market cycles",
            "Risk-thinking frameworks",
            "FinSight Q&A mode (education + concepts)",
            "Market explainers (no signals, no calls)",
        ],
        "icon": "brain",
    },
    {
        "level": 3,
        "name": "Premium",
        "description": "Think in systems. Understand context.",
        "price_amount": 7900,
        "highlights": [
            "Everything in Investor Mindset",
            "FinSight interactive intelligence",
            "Scenario analysis & macro context",
            "Risk framework explanations",
            "Portfolio logic (non-personalised)",
        ],
        "is_popular": True,
        "icon": "star",
    },
    {
        "level": 4,
        "name": "Enterprise",
        "description": "Interpret markets like professionals do.",
        "price_amount": 14900,
        "highlights": [
            "Everything in FinSight Intelligence",
            "FinSight signals-aware intelligence",
            "Explanation of what models are indicating",
            "How professionals interpret data",
            "Priority FinSight compute & faster responses",
        ],
        "icon": "energy",
    },
]

TIER_ENTITLEMENTS = {
    1: [
        "CHAT_ACCESS_BASIC",
        "MEMORY_NONE",
        "INSIGHTS_NONE",
        "SIGNALS_NONE",
        "ADVISORY_DISABLED",
    ],
    2: [
        "CHAT_ACCESS_EXTENDED",
        "MEMORY_SHORT",
        "INSIGHTS_BASIC",
        "SIGNALS_EDUCATIONAL",
    ],
    3: ["MEMORY_LONG", "INSIGHTS_PORTFOLIO"],
    4: ["CHAT_ACCESS_PRIORITY", "INSIGHTS_PRO", "SIGNALS_AI", "BRIEFINGS_WEEKLY"],
}


def seed_database():
    # Make sure all tables are created
    Base.metadata.create_all(bind=engine)

    db = SESSION_LOCAL()
    try:
        print("[SEEDING] Seeding Roles...")
        role_user = db.query(Role).filter_by(role=UserRole.USER).first()
        if not role_user:
            role_user = Role(id=1, role=UserRole.USER)
            db.add(role_user)

        role_admin = db.query(Role).filter_by(role=UserRole.ADMIN).first()
        if not role_admin:
            role_admin = Role(id=2, role=UserRole.ADMIN)
            db.add(role_admin)

        db.flush()

        print("[SEEDING] Seeding Entitlements...")
        ent_map = {}
        for code, desc in ENTITLEMENTS:
            ent = db.query(Entitlements).filter_by(code=code).first()
            if not ent:
                ent = Entitlements(code=code, description=desc)
                db.add(ent)
                db.flush()
            ent_map[code] = ent

        print("[SEEDING] Seeding Tiers...")
        tier_map = {}
        for t_data in TIER_CATALOG:
            level = t_data["level"]
            tier = db.query(Tier).filter_by(level=level).first()
            if not tier:
                tier = Tier(level=level)
                db.add(tier)

            tier.name = t_data["name"]
            tier.description = t_data["description"]
            tier.price_amount = t_data["price_amount"]
            tier.price_amount_yearly = int(t_data["price_amount"] * 12 * 0.9)
            tier.currency = "usd"
            tier.highlights = t_data.get("highlights")
            tier.is_popular = t_data.get("is_popular", False)
            tier.icon = t_data.get("icon")

            db.flush()
            tier_map[level] = tier

        print("[SEEDING] Seeding Tier Entitlements mapping...")
        for level, codes in TIER_ENTITLEMENTS.items():
            tier = tier_map[level]
            for code in codes:
                entitlement = ent_map[code]
                exists = (
                    db.query(TierEntitlement)
                    .filter_by(tier_id=tier.id, entitlement_id=entitlement.id)
                    .first()
                )
                if not exists:
                    db.add(
                        TierEntitlement(tier_id=tier.id, entitlement_id=entitlement.id)
                    )

        db.flush()

        print("[SEEDING] Creating Test Users...")
        # Dictionary of emails and their respective subscription levels
        test_users = {
            "starter@example.com": 1,
            "growth@example.com": 2,
            "premium@example.com": 3,
            "enterprise@example.com": 4,
        }

        # Shared password for easy testing
        plain_password = "password123"
        hashed = hash_password(plain_password)

        for email, tier_level in test_users.items():
            user = db.query(User).filter_by(email=email).first()
            if not user:
                user = User(
                    email=email,
                    password_hash=hashed,
                    is_verified=True,
                    status=UserStatus.ACTIVE,
                    role_id=role_user.id,
                )
                db.add(user)
                db.flush()

            # Ensure subscription is set to specified tier
            sub = db.query(Subscription).filter_by(user_id=user.id).first()
            if not sub:
                sub = Subscription(
                    user_id=user.id,
                    tier_id=tier_map[tier_level].id,
                    status=SubscriptionStatus.ACTIVE,
                    source=SubscriptionSource.FREE,
                )
                db.add(sub)
            else:
                sub.tier_id = tier_map[tier_level].id
                sub.status = SubscriptionStatus.ACTIVE

        # Also create an admin user
        admin_email = "admin@example.com"
        admin_user = db.query(User).filter_by(email=admin_email).first()
        if not admin_user:
            admin_user = User(
                email=admin_email,
                password_hash=hashed,
                is_verified=True,
                status=UserStatus.ACTIVE,
                role_id=role_admin.id,
            )
            db.add(admin_user)
            db.flush()

        # Give admin Pro/Enterprise tier access
        admin_sub = db.query(Subscription).filter_by(user_id=admin_user.id).first()
        if not admin_sub:
            admin_sub = Subscription(
                user_id=admin_user.id,
                tier_id=tier_map[4].id,
                status=SubscriptionStatus.ACTIVE,
                source=SubscriptionSource.ADMIN,
            )
            db.add(admin_sub)

        db.commit()
        print("[SUCCESS] Database seeded successfully with test users!")

        print("\n--- Seeded Accounts (Password: 'password123') ---")
        for email, tier_level in test_users.items():
            print(f"Tier {tier_level} ({tier_map[tier_level].name}): {email}")
        print(f"Admin User (Tier Enterprise): {admin_email}")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
