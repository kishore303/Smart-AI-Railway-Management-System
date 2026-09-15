from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserBrief,
    MeResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.models.user import User
from app.models.department import Department
from app.core.security import verify_password, hash_password, create_access_token, create_reset_token, decode_token
from app.core.rbac import get_current_active_user
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _audit(db: Session, user_id, action: str, description: str = None, entity_type: str = None):
    from app.models.audit import AuditLog

    log = AuditLog(user_id=user_id, action=action, entity_type=entity_type, description=description)
    db.add(log)
    db.commit()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # username can be email or name — spec says username/email
    user = db.query(User).filter((User.email == payload.username) | (User.name == payload.username)).first()
    if not user:
        _audit(db, None, "LOGIN_FAILED", f"Unknown user: {payload.username}", entity_type="user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        _audit(db, user.id, "LOGIN_FAILED_INACTIVE", entity_type="user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account inactive")

    if not verify_password(payload.password, user.password_hash):
        _audit(db, user.id, "LOGIN_FAILED", "Wrong password", entity_type="user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    dept = db.query(Department).filter(Department.id == user.department_id).first()
    dept_code = dept.code if dept else "UNKNOWN"
    dept_name = dept.name if dept else "UNKNOWN"

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token_data = {
        "user_id": user.id,
        "email": user.email,
        "department": dept_name,
        "department_code": dept_code,
        "department_id": user.department_id,
        "role": user.role,
    }
    token = create_access_token(token_data)

    _audit(db, user.id, "LOGIN", f"User {user.email} logged in as {user.role}@{dept_code}", entity_type="user")

    user_brief = UserBrief(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department=dept_code,
        department_id=user.department_id,
        is_active=user.is_active,
    )
    return LoginResponse(access_token=token, user=user_brief, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == current_user.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return MeResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        department=code,
        department_id=current_user.department_id,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return success to avoid enumeration — spec: never expose credentials
    if not user:
        return ForgotPasswordResponse(message="If the email exists, a reset link has been sent.")

    token = create_reset_token(user.email, expires_minutes=15)
    _audit(db, user.id, "FORGOT_PASSWORD", f"Password reset requested for {user.email}", entity_type="user")
    # In production this would email token; in dev we return it for testing
    # Never log token in plaintext logs in production (here we avoid logging token)
    if settings.app_env == "development":
        return ForgotPasswordResponse(message="Reset token generated (dev mode).", reset_token=token)
    return ForgotPasswordResponse(message="If the email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.token)
        if data.get("purpose") != "password_reset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token purpose")
        email = data.get("sub")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update password
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    _audit(db, user.id, "RESET_PASSWORD", "Password reset via token", entity_type="user")
    return ResetPasswordResponse(message="Password has been reset successfully")
