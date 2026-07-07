# scripts/seed_tier_token_configs.py

from sqlalchemy.orm import Session

from app.core.database import SESSION_LOCAL
from app.models.tiers import Tier
from app.models.tokens import TierTokenConfig


# Default token configuration per tier
TIER_TOKEN_CONFIG = {
    1: {
        "weekly_tokens": 375000,
        "daily_token_limit": 50000,
        "monthly_token_limit": 1500000,
        "refill_frequency": "weekly",
        "max_tokens_per_prompt": 2000,
    },

    2: {
        "weekly_tokens": 11250000,
        "daily_token_limit": 1500000,
        "monthly_token_limit": 45000000,
        "refill_frequency": "weekly",
        "max_tokens_per_prompt": 5000,
    },

    3: {
        "weekly_tokens": 18750000,
        "daily_token_limit": 2500000,
        "monthly_token_limit": 75000000,
        "refill_frequency": "weekly",
        "max_tokens_per_prompt": 10000,
    },

    4: {
        "weekly_tokens": 37500000,
        "daily_token_limit": 5000000,
        "monthly_token_limit": 150000000,
        "refill_frequency": "weekly",
        "max_tokens_per_prompt": 20000,
    },

}

DEFAULT_CONFIG = {
    "weekly_tokens": 2500000,
    "daily_token_limit": 350000,
    "monthly_token_limit": 10000000,
    "refill_frequency": "weekly",
    "max_tokens_per_prompt": 3000,
}


def seed_tier_token_configs():

    db: Session = SESSION_LOCAL()

    try:

        tiers = db.query(Tier).all()

        if not tiers:
            print("No tiers found in tiers table.")
            return

        for tier in tiers:

            # Get config for tier
            config = TIER_TOKEN_CONFIG.get(
                tier.level,
                DEFAULT_CONFIG,
            )

            existing_config = (
                db.query(TierTokenConfig)
                .filter(
                    TierTokenConfig.tier_id == tier.id
                )
                .first()
            )

            # -----------------------------
            # UPDATE EXISTING CONFIG
            # -----------------------------
            if existing_config:

                existing_config.weekly_tokens = config["weekly_tokens"]

                existing_config.daily_token_limit = config[
                    "daily_token_limit"
                ]

                existing_config.monthly_token_limit = config[
                    "monthly_token_limit"
                ]

                existing_config.refill_frequency = config[
                    "refill_frequency"
                ]

                existing_config.max_tokens_per_prompt = config[
                    "max_tokens_per_prompt"
                ]

                print(
                    f"Updated token config for tier: {tier.name}"
                )

            # -----------------------------
            # CREATE NEW CONFIG
            # -----------------------------
            else:

                token_config = TierTokenConfig(
                    id=tier.id,
                    tier_id=tier.id,
                    weekly_tokens=config["weekly_tokens"],
                    daily_token_limit=config[
                        "daily_token_limit"
                    ],
                    monthly_token_limit=config[
                        "monthly_token_limit"
                    ],
                    refill_frequency=config[
                        "refill_frequency"
                    ],
                    max_tokens_per_prompt=config[
                        "max_tokens_per_prompt"
                    ],
                )

                db.add(token_config)

                print(
                    f"Created token config for tier: {tier.name}"
                )

        db.commit()

        print(
            "Tier token config seeding completed successfully."
        )

    except Exception as e:

        db.rollback()

        print(
            f"Error while seeding tier token configs: {str(e)}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    seed_tier_token_configs()