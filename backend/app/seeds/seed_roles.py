from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.users import Role, UserRole

SESSION_LOCAL = sessionmaker(bind=engine)


def seed_roles():
    db = SESSION_LOCAL()
    try:
        print("Seeding Roles...")

        roles_to_seed = [UserRole.ADMIN, UserRole.USER]

        for role_enum in roles_to_seed:
            existing_role = db.query(Role).filter(Role.role == role_enum).first()

            if not existing_role:
                print(f"  > Creating role: {role_enum.value}")
                new_role = Role(role=role_enum)
                db.add(new_role)
            else:
                print(f"  > Role already exists: {role_enum.value}")

        db.commit()
        print("Roles seeded successfully.")

    except SQLAlchemyError as exc:
        print(f"Database error seeding roles: {exc}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
