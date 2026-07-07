from app.seeds.seed_roles import seed_roles
from app.seeds.seed_compliance import seed_compliance
from app.seeds.seed_cip_questions import seed_cip_questions
from app.seeds.seed_tiers import seed_tiers


def confirm_step(name):
    """Ask user for confirmation."""
    while True:
        choice = input(f"❓ Run {name} seed? (y/n): ").lower().strip()
        if choice in ["y", "yes"]:
            return True
        if choice in ["n", "no"]:
            return False


def run():
    print("🌱 Starting database seeding process...")

    if confirm_step("Roles"):
        seed_roles()

    if confirm_step("Tiers"):
        seed_tiers()

    if confirm_step("Compliance"):
        seed_compliance()

    if confirm_step("CIP and Additional Questions"):
        seed_cip_questions()

    print("✅ Seeding process completed.")


if __name__ == "__main__":
    run()
