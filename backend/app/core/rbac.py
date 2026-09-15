from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.core.security import decode_token
from app.core.config import settings
from app.models.user import User
from app.models.department import Department

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Canonical department-role mappings per SIH26027 spec
# code -> allowed roles
DEPARTMENT_ROLES = {
    "ENG": {"MAINTENANCE_STAFF", "ENGINEER_REVIEWER"},
    "ELEC": {"MAINTENANCE_STAFF", "ENGINEER_REVIEWER"},
    "SNT": {"MAINTENANCE_STAFF", "ENGINEER_REVIEWER"},
    "OPS": {"OPERATOR"},
    "CONTROL": {"CONTROLLER"},
    "RAILWAY": {"AUTHORIZED_OFFICIAL"},
    "EMERGENCY": {"EMERGENCY_OPERATOR"},
}

# Role permissions (backend-enforced, not just UI)
ROLE_PERMISSIONS = {
    "MAINTENANCE_STAFF": {
        "maintenance:create",
        "maintenance:read:own",
        "maintenance:read:department",
        "block:read",
    },
    "ENGINEER_REVIEWER": {
        "maintenance:review",
        "maintenance:read:department",
        "block:read",
        "integration:respond",
    },
    "OPERATOR": {
        "block:read",
        "train:read",
        "maintenance:read",
    },
    "CONTROLLER": {
        "block:read",
        "block:coordinate",
        "train:read",
        "incident:read",
    },
    "AUTHORIZED_OFFICIAL": {
        "block:approve",
        "block:modify",
        "block:reject",
        "block:read:all",
        "maintenance:read:all",
        "audit:read",
        "integration:read:all",
    },
    "EMERGENCY_OPERATOR": {
        "incident:create",
        "incident:read:all",
        "emergency:respond",
        "block:read:all",
    },
}


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id") or payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        # token must contain exp already validated by decode_token
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    # Verify department/role in token still matches DB (prevent stale role)
    token_dept = payload.get("department_code") or payload.get("department")
    token_role = payload.get("role")
    # Fetch actual dept code
    dept = db.query(Department).filter(Department.id == user.department_id).first()
    actual_code = dept.code if dept else None
    if token_role != user.role or (token_dept and token_dept != actual_code):
        # Force re-login on mismatch — token revoked
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token role mismatch, please re-login")

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user


def require_roles(*allowed_roles: str):
    def checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role {current_user.role} not allowed. Required: {allowed_roles}")
        return current_user

    return checker


def require_permissions(*perms: str):
    def checker(current_user: User = Depends(get_current_active_user)):
        user_perms = ROLE_PERMISSIONS.get(current_user.role, set())
        for p in perms:
            if p not in user_perms:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission {p} required for role {current_user.role}")
        return current_user

    return checker


def require_department(*codes: str):
    def checker(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
        dept = db.query(Department).filter(Department.id == current_user.department_id).first()
        if not dept or dept.code not in codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Department {dept.code if dept else 'unknown'} not allowed")
        return current_user

    return checker


def can_access_department_resource(current_user: User, resource_department_id: int, db: Session) -> bool:
    """Department-scoped access: same dept, or AUTHORIZED_OFFICIAL/EMERGENCY/CONTROL can read all."""
    if current_user.role in ("AUTHORIZED_OFFICIAL", "EMERGENCY_OPERATOR", "CONTROLLER"):
        return True
    return current_user.department_id == resource_department_id


def check_self_approval(current_user_id: int, requested_by_id: int):
    """Mandatory server-side self-approval protection."""
    if current_user_id == requested_by_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval prohibited: requester cannot approve own work")


def is_valid_department_role(dept_code: str, role: str) -> bool:
    return role in DEPARTMENT_ROLES.get(dept_code, set())
