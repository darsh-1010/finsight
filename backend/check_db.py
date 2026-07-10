from app.core.database import SessionLocal
from app.models.users import User, UserVerificationToken

db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(f"User: {u.email}, is_verified: {u.is_verified}")

tokens = db.query(UserVerificationToken).all()
for t in tokens:
    print(f"Token: {t.token}, user_id: {t.user_id}, type: {t.token_type}")
