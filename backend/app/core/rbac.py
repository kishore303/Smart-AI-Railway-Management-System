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

# Canonical department-role mappings per SIH26027 spec (13 combinations)
# code -> allowed roles
DEPARTMENT_ROLES = {
    "ENG": {"MAINTENANCE_STAFF", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "ELEC": {"MAINTENANCE_STAFF", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "SNT": {"MAINTENANCE_STAFF", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
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
        "asset:read",
        "notification:read",
    },
    "JUNIOR_ENGINEER": {
        "maintenance:review:initial",
        "maintenance:read:department",
        "block:read",
        "asset:read",
        "coordination:read",
        "notification:read",
    },
    "SENIOR_SECTION_ENGINEER": {
        "maintenance:review:senior",
        "maintenance:read:department",
        "maintenance:forward:planning",
        "block:read",
        "block:create",
        "integration:respond",
        "coordination:manage",
        "resources:read",
        "notification:read",
    },
    "OPERATOR": {
        "train:read",
        "timetable:read",
        "conflict:read",
        "train_impact:read",
        "block:read",
        "maintenance:read",
        "notification:read",
    },
    "CONTROLLER": {
        "block:read:all",
        "block:coordinate",
        "execution:manage",
        "train:read",
        "incident:read",
        "coordination:read",
        "notification:read",
    },
    "AUTHORIZED_OFFICIAL": {
        "block:approve",
        "block:modify",
        "block:reject",
        "block:read:all",
        "maintenance:read:all",
        "ai_recommendations:read",
        "safety_results:read",
        "audit:read",
        "integration:read:all",
        "simulation:manage",
        "digital_twin:read",
        "emergency:read:all",
        "notification:read",
    },
    "EMERGENCY_OPERATOR": {
        "incident:create",
        "incident:read:all",
        "emergency:respond",
        "emergency:replanning",
        "block:read:all",
        "notification:read",
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


def check_self_approval(current_user_id: int, requested_by_id: int, reviewer_id: int = None):
    """Mandatory server-side self-approval protection."""
    if current_user_id == requested_by_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval prohibited: requester cannot approve own work")
    if reviewer_id is not None and current_user_id == reviewer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval prohibited: reviewer cannot perform final approval")


def is_valid_department_role(dept_code: str, role: str) -> bool:
    return role in DEPARTMENT_ROLES.get(dept_code, set())
