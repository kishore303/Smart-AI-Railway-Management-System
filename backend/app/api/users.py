from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user, require_roles, can_access_department_resource, is_valid_department_role, DEPARTMENT_ROLES
from app.core.security import verify_password, hash_password
from app.models.user import User
from app.models.department import Department
from app.models.audit import AuditLog
from app.schemas.user import UserOut, UserSelfUpdate, ChangePasswordRequest, ChangePasswordResponse, AdminUserUpdate, UserListResponse, UserListItem

router = APIRouter(prefix="/api/users", tags=["users"])


def _audit(db: Session, user_id, action: str, entity_type: str = "user", entity_id: int = None, description: str = None):
    log = AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, description=description)
    db.add(log)
    db.commit()


def _to_user_out(user: User, dept_code: str) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department=dept_code,
        department_id=user.department_id,
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == current_user.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return _to_user_out(current_user, code)


@router.put("/me", response_model=UserOut)
def update_me(payload: UserSelfUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Only name allowed for self — role/department/email/is_active are locked
    if payload.name is not None:
        old_name = current_user.name
        current_user.name = payload.name.strip()
        db.commit()
        db.refresh(current_user)
        _audit(db, current_user.id, "UPDATE_PROFILE", entity_id=current_user.id, description=f"name: {old_name} -> {current_user.name}")
    dept = db.query(Department).filter(Department.id == current_user.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return _to_user_out(current_user, code)


@router.post("/me/change-password", response_model=ChangePasswordResponse)
def change_password(payload: ChangePasswordRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not verify_password(payload.old_password, current_user.password_hash):
        _audit(db, current_user.id, "CHANGE_PASSWORD_FAILED", entity_id=current_user.id, description="old password mismatch")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    _audit(db, current_user.id, "CHANGE_PASSWORD", entity_id=current_user.id, description="password changed via profile")
    return ChangePasswordResponse(message="Password updated successfully")


@router.get("/admin/only-official")
def only_official(current_user: User = Depends(require_roles("AUTHORIZED_OFFICIAL"))):
    return {"message": f"Hello official {current_user.name}", "role": current_user.role}


@router.get("", response_model=UserListResponse)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    department_code: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="search name/email"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # RBAC: AUTHORIZED_OFFICIAL / CONTROLLER / EMERGENCY can see all, others only own department
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "EMERGENCY_OPERATOR")
    query = db.query(User)

    if not is_privileged:
        query = query.filter(User.department_id == current_user.department_id)
        # Non-privileged cannot override department_code to cross-dept
        if department_code:
            # Check if requested dept is same as own
            own_dept = db.query(Department).filter(Department.id == current_user.department_id).first()
            if department_code != own_dept.code:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department filter denied")
    else:
        if department_code:
            dept = db.query(Department).filter(Department.code == department_code).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
            query = query.filter(User.department_id == dept.id)

    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if q:
        like = f"%{q}%"
        query = query.filter((User.name.ilike(like)) | (User.email.ilike(like)))

    total = query.count()
    users = query.order_by(User.id).offset(skip).limit(limit).all()

    items = []
    for u in users:
        dept = db.query(Department).filter(Department.id == u.department_id).first()
        code = dept.code if dept else "UNKNOWN"
        items.append(UserListItem(id=u.id, name=u.name, email=u.email, role=u.role, department=code, department_id=u.department_id, is_active=u.is_active))
    return UserListResponse(total=total, items=items, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not can_access_department_resource(current_user, target.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    dept = db.query(Department).filter(Department.id == target.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return _to_user_out(target, code)


@router.patch("/{user_id}", response_model=UserOut)
def admin_update_user(user_id: int, payload: AdminUserUpdate, current_user: User = Depends(require_roles("AUTHORIZED_OFFICIAL")), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Sensitive-field protection: never allow password_hash direct set via this endpoint
    # Prevent role/dept self-escalation ambiguity already handled by official-only

    changes = []
    if payload.name is not None:
        changes.append(f"name:{target.name}->{payload.name.strip()}")
        target.name = payload.name.strip()

    if payload.is_active is not None:
        changes.append(f"is_active:{target.is_active}->{payload.is_active}")
        target.is_active = payload.is_active

    # Department/role update must be paired and validated against department_roles
    if payload.department_code is not None or payload.role is not None:
        new_dept_code = payload.department_code if payload.department_code is not None else db.query(Department).filter(Department.id == target.department_id).first().code
        new_role = payload.role if payload.role is not None else target.role

        if new_dept_code not in DEPARTMENT_ROLES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown department {new_dept_code}")
        if not is_valid_department_role(new_dept_code, new_role):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid role {new_role} for department {new_dept_code}")

        new_dept = db.query(Department).filter(Department.code == new_dept_code).first()
        if not new_dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        # Verify FK exists in department_roles
        from app.models.department import DepartmentRole

        exists = db.query(DepartmentRole).filter(DepartmentRole.department_id == new_dept.id, DepartmentRole.role == new_role).first()
        if not exists:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Department-role pair not allowed")

        old_dept_code = db.query(Department).filter(Department.id == target.department_id).first().code
        changes.append(f"dept:{old_dept_code}->{new_dept_code}")
        changes.append(f"role:{target.role}->{new_role}")
        target.department_id = new_dept.id
        target.role = new_role

    if changes:
        db.commit()
        db.refresh(target)
        _audit(db, current_user.id, "ADMIN_UPDATE_USER", entity_id=target.id, description="; ".join(changes))

    dept = db.query(Department).filter(Department.id == target.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return _to_user_out(target, code)
