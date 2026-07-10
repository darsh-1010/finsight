from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SESSION_LOCAL
from app.models.users import User

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/access-token",
    auto_error=False,
)


def get_db():
    db = SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
):
    # 1. Try getting token from Bearer Header (Swagger UI uses this)
    if not token:
        # 2. Fallback to Cookie (Frontend uses this)
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def require_role(role_name: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role.role != role_name:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return checker
