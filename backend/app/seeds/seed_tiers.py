from sqlalchemy.orm import Session
from app.core.database import SESSION_LOCAL
from app.models.tiers import Tier, Entitlements, TierEntitlement

# -------------------------
# SEED DATA (UNCHANGED)
# -------------------------

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
    1: ["CHAT_ACCESS_BASIC", "MEMORY_NONE", "INSIGHTS_NONE",
        "SIGNALS_NONE", "ADVISORY_DISABLED"],
    2: ["CHAT_ACCESS_EXTENDED", "MEMORY_SHORT", "INSIGHTS_BASIC",
        "SIGNALS_EDUCATIONAL"],
    3: ["MEMORY_LONG", "INSIGHTS_PORTFOLIO"],
    4: ["CHAT_ACCESS_PRIORITY", "INSIGHTS_PRO", "SIGNALS_AI",
        "BRIEFINGS_WEEKLY"],
}

def _sync_entitlements(db: Session):
    ent_map = {}

    for code, desc in ENTITLEMENTS:
        ent = (
            db.query(Entitlements)
            .filter_by(code=code)
            .first()
            or db.merge(Entitlements(code=code, description=desc))
        )
        ent_map[code] = ent

    db.flush()
    return ent_map

def _sync_tiers(db: Session):
    tier_map = {}

    for t_data in TIER_CATALOG:
        level = t_data["level"]
        monthly = t_data["price_amount"]
        yearly = int(monthly * 12 * 0.9) if monthly > 0 else 0

        tier = db.query(Tier).filter_by(level=level).first() or Tier(level=level)
        if not tier.id:
            db.add(tier)

        tier.name = t_data["name"]
        tier.description = t_data["description"]
        tier.price_amount = monthly
        tier.price_amount_yearly = yearly
        tier.currency = "usd"
        tier.stripe_product_id = f"mock_prod_{level}"
        tier.stripe_price_id = f"mock_price_{level}"
        tier.stripe_yearly_price_id = f"mock_yearly_{level}" if yearly > 0 else None
        tier.highlights = t_data.get("highlights")
        tier.is_popular = t_data.get("is_popular", False)
        tier.icon = t_data.get("icon")

        db.flush()
        tier_map[level] = tier

    return tier_map

def _sync_tier_entitlements(db: Session, tier_map, ent_map):
    for level, codes in TIER_ENTITLEMENTS.items():
        tier = tier_map[level]

        for code in codes:
            entitlement = ent_map[code]

            exists = db.query(TierEntitlement).filter_by(
                tier_id=tier.id,
                entitlement_id=entitlement.id,
            ).first()

            if not exists:
                db.add(
                    TierEntitlement(
                        tier_id=tier.id,
                        entitlement_id=entitlement.id,
                    )
                )

def seed_tiers():
    """Sync tiers and entitlements."""
    db: Session = SESSION_LOCAL()

    try:
        ent_map = _sync_entitlements(db)
        tier_map = _sync_tiers(db)
        _sync_tier_entitlements(db, tier_map, ent_map)

        db.commit()
        print("[SUCCESS] DB tiers synced successfully (without Stripe)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_tiers()
