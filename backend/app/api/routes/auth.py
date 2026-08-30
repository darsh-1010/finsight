import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.subscriptions import ChangeSource, ChangeType
from app.models.tiers import Tier
from app.models.users import (
    Role,
    User,
    UserRole,
    UserSession,
    UserVerificationToken,
    VisitingUser,
)
from app.schemas.users import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
    UserOut,
    VisitingUserChatCountUpdate,
    VisitingUserCreate,
    VisitingUserOut,
)
from app.services.entitlement_service import EntitlementService
from app.services.ses_service import ses_service
from app.services.tier_service import TierService
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/visiting-users", response_model=VisitingUserOut)
def create_visiting_user(
    data: VisitingUserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=400,
            detail="You already have an account. Please login.",
        )

    existing_visiting_user = (
        db.query(VisitingUser).filter(VisitingUser.email == data.email).first()
    )
    if existing_visiting_user:
        response.status_code = 200
        return existing_visiting_user

    visiting_user = VisitingUser(email=data.email)
    db.add(visiting_user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Visiting user already exists",
        ) from exc

    db.refresh(visiting_user)
    response.status_code = 201
    return visiting_user


@router.patch(
    "/visiting-users/{visiting_user_id}/chat-count",
    response_model=VisitingUserOut,
)
def update_visiting_user_chat_count(
    visiting_user_id: int,
    data: VisitingUserChatCountUpdate,
    db: Session = Depends(get_db),
):
    visiting_user = (
        db.query(VisitingUser).filter(VisitingUser.id == visiting_user_id).first()
    )

    if not visiting_user:
        raise HTTPException(status_code=404, detail="Visiting user not found")

    visiting_user.chat_count = data.chat_count
    visiting_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(visiting_user)

    return visiting_user


@router.post("/access-token")
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access = create_access_token({"sub": str(user.id), "role": user.role.role.value})
    refresh = create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return {
        "access_token": access,
        "token_type": "bearer",
        "refresh_token": refresh,
    }


@router.post("/signup")
def signup(data: UserCreate, response: Response, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already exists")

    # Public signup always gets the standard user role - never trust a client-supplied
    # role_id (the "user" vs "admin" role ids aren't a stable/documented contract, and
    # accepting one from the request let any signup request itself as an admin).
    role = db.query(Role).filter(Role.role == UserRole.USER).first()
    if not role:
        raise HTTPException(500, "Server misconfiguration: default user role not seeded")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=role.id,
    )

    db.add(user)
    db.flush()

    subscription = TierService.assign_default_subscription(db=db, user=user)

    # Token wallet for the Foundation tier assigned above.
    signup_tier = db.query(Tier).filter(Tier.id == subscription.tier_id).first()
    if signup_tier:
        TokenService.create_wallet_for_user(
            db,
            user,
            signup_tier,
            transaction_type="signup_bonus",
        )

    tier_name = "Foundation"
    tier_features = ["Access to basic features", "Community support"]

    if data.tier_level and data.tier_level > 1:
        requested_tier = db.query(Tier).filter(Tier.level == data.tier_level).first()

        if not requested_tier:
            raise HTTPException(status_code=400, detail="Invalid tier selected")

        # Every tier is free, so apply the requested plan immediately - no checkout step.
        subscription = TierService.change_tier(
            db,
            user,
            data.tier_level,
            change_type=ChangeType.UPGRADE,
            source=ChangeSource.SYSTEM,
        )
        tier_name = requested_tier.name
        if requested_tier.highlights:
            tier_features = requested_tier.highlights
    else:
        foundation_tier = db.query(Tier).filter(Tier.level == 1).first()
        if foundation_tier:
            tier_name = foundation_tier.name
            if foundation_tier.highlights:
                tier_features = foundation_tier.highlights

    access = create_access_token({"sub": str(user.id), "role": user.role.role.value})
    refresh = create_refresh_token({"sub": str(user.id)})

    db.add(
        UserSession(
            user_id=user.id,
            token_hash=refresh,
            expires_at=datetime.utcnow()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )

    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    db.add(
        UserVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            token_type="verification",
        )
    )

    db.commit()

    # Send verification email immediately for all tiers
    try:
        ses_service.send_verification_email(
            user.email,
            verification_token,
            tier_name=tier_name,
            tier_features=tier_features,
        )
    except Exception as e:
        # Log error but don't fail signup
        print(f"Failed to send verification email: {e}")

    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return {
        "message": "User created successfully",
        "user_id": user.id,
        "effective_tier_id": subscription.tier_id,
        "subscription_status": subscription.status,
    }


@router.post("/login")
def login(data: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    if not user.is_verified:
        active_token = (
            db.query(UserVerificationToken)
            .filter(
                UserVerificationToken.user_id == user.id,
                UserVerificationToken.token_type == "verification",
                UserVerificationToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not active_token:
            verification_token = secrets.token_urlsafe(32)
            db.add(
                UserVerificationToken(
                    user_id=user.id,
                    token=verification_token,
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                    token_type="verification",
                )
            )
            db.commit()

            tier_name = "Foundation"
            tier_features = ["Access to basic features", "Community support"]
            if user.subscription and user.subscription.tier:
                tier_name = user.subscription.tier.name
                if user.subscription.tier.highlights:
                    tier_features = user.subscription.tier.highlights

            try:
                ses_service.send_verification_email(
                    user_email=user.email,
                    token=verification_token,
                    tier_name=tier_name,
                    tier_features=tier_features,
                )
            except Exception as e:
                print(f"Failed to send automated verification email on login: {e}")

    access = create_access_token({"sub": str(user.id), "role": user.role.role.value})
    refresh = create_refresh_token({"sub": str(user.id)})

    db.add(
        UserSession(
            user_id=user.id,
            token_hash=refresh,
            expires_at=datetime.utcnow()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()

    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return {"message": "Login successful"}


@router.get("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Missing refresh token")

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = int(payload.get("sub"))
    except JWTError as exc:
        raise HTTPException(401, "Invalid refresh token") from exc

    db_token = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.token_hash == token,
            UserSession.revoked.is_(False),
            UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not db_token:
        raise HTTPException(401, "Refresh token revoked or expired")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token(
        {"sub": str(user.id), "role": user.role.role.value}
    )
    new_refresh_token = create_refresh_token({"sub": str(user.id)})

    db_token.token_hash = new_refresh_token
    db_token.expires_at = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db.commit()

    response.set_cookie(
        "access_token",
        new_access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        "refresh_token",
        new_refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return {"message": "Token refreshed"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entitlements = EntitlementService.get_user_entitlements(db, user.id)

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.role.value,
        "tier_level": user.subscription.tier.level,
        "tier_name": user.subscription.tier.name,
        "entitlements": entitlements,
        "is_onboarded": True,
        "is_verified": user.is_verified,
        "experience_level": getattr(user.profile, "experience_level", "") or "",
        "risk_level": getattr(user.profile, "risk_bucket", "") or "",
        "updated_at": user.updated_at,
    }


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    user.password_hash = hash_password(data.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


@router.get("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")

    if token:
        db.query(UserSession).filter(UserSession.token_hash == token).update(
            {"revoked": True}
        )
        db.commit()

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return {"message": "Logged out"}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal if user exists or not for security
        return {
            "message": "If an account exists with this email, a reset link has been sent."
        }

    # Revoke old reset tokens
    db.query(UserVerificationToken).filter(
        UserVerificationToken.user_id == user.id,
        UserVerificationToken.token_type == "password_reset",
    ).delete()

    reset_token = secrets.token_urlsafe(32)
    db.add(
        UserVerificationToken(
            user_id=user.id,
            token=reset_token,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            token_type="password_reset",
        )
    )
    db.commit()

    try:
        ses_service.send_password_reset_email(user.email, reset_token)
    except Exception as e:
        print(f"Failed to send reset email: {e}")

    return {
        "message": "If an account exists with this email, a reset link has been sent."
    }


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_record = (
        db.query(UserVerificationToken)
        .filter(
            UserVerificationToken.token == data.token,
            UserVerificationToken.token_type == "password_reset",
            UserVerificationToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = hash_password(data.new_password)

    # Revoke the used token
    db.delete(token_record)
    db.commit()

    return {"message": "Password reset successfully"}


@router.get("/verify-email")
def verify_email(
    token: str, request: Request, response: Response, db: Session = Depends(get_db)
):
    token_record = (
        db.query(UserVerificationToken)
        .filter(
            UserVerificationToken.token == token,
            UserVerificationToken.token_type == "verification",
            UserVerificationToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not token_record:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token"
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.is_verified = True

    # Revoke the used token
    db.delete(token_record)

    # Check if the user already has a valid session on this device
    cookie_token = request.cookies.get("refresh_token")
    has_valid_session = False
    if cookie_token:
        try:
            payload = jwt.decode(
                cookie_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            session_user_id = int(payload.get("sub"))
            if session_user_id == user.id:
                db_token = (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user.id,
                        UserSession.token_hash == cookie_token,
                        UserSession.revoked.is_(False),
                        UserSession.expires_at > datetime.utcnow(),
                    )
                    .first()
                )
                if db_token:
                    has_valid_session = True
        except JWTError:
            pass

    # Auto-login: issue new tokens only if they don't have a valid session
    if not has_valid_session:
        access = create_access_token(
            {"sub": str(user.id), "role": user.role.role.value}
        )
        refresh = create_refresh_token({"sub": str(user.id)})

        db.add(
            UserSession(
                user_id=user.id,
                token_hash=refresh,
                expires_at=datetime.utcnow()
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )

        response.set_cookie(
            "access_token",
            access,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
        )
        response.set_cookie(
            "refresh_token",
            refresh,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
        )

    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
def resend_verification(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    # Revoke old verification tokens
    db.query(UserVerificationToken).filter(
        UserVerificationToken.user_id == user.id,
        UserVerificationToken.token_type == "verification",
    ).delete()

    verification_token = secrets.token_urlsafe(32)
    db.add(
        UserVerificationToken(
            user_id=user.id,
            token=verification_token,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            token_type="verification",
        )
    )
    db.commit()

    tier_name = "Foundation"
    tier_features = ["Access to basic features", "Community support"]
    if user.subscription and user.subscription.tier:
        tier_name = user.subscription.tier.name
        if user.subscription.tier.highlights:
            tier_features = user.subscription.tier.highlights

    try:
        ses_service.send_verification_email(
            user_email=user.email,
            token=verification_token,
            tier_name=tier_name,
            tier_features=tier_features,
        )
    except Exception as exc:
        logger.error("[VERIFICATION_EMAIL_FAIL] User: %s | Error: %s", user.id, exc)
        raise HTTPException(
            status_code=500, detail="Failed to send verification email"
        ) from exc

    return {"message": "Verification email sent successfully"}
