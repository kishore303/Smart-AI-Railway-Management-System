from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.safety.engine import validate_candidate, revalidate_candidate, get_safe_candidates

router = APIRouter(prefix="/api/safety", tags=["safety"])

# Roles allowed to validate — not MAINTENANCE_STAFF (to prevent bypass)
ALLOWED_ROLES = {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "CONTROLLER", "AUTHORIZED_OFFICIAL", "EMERGENCY_OPERATOR"}


def _audit(db: Session, user_id, action, entity_id=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="safety_validation", entity_id=entity_id, description=desc)
    db.add(log)
    db.commit()


@router.post("/validate/candidate/{candidate_id}")
def validate_candidate_endpoint(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot perform safety validation")
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role != "AUTHORIZED_OFFICIAL" and current_user.department_id != (mreq.department_id if mreq else None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    result = validate_candidate(cand, db, user_id=current_user.id, persist=True)
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == candidate_id).first()

    return {
        "candidate_id": candidate_id,
        "block_request_id": cand.block_request_id,
        "overall_status": sv.overall_status if sv else result["overall_status"],
        "is_safe_for_optimization": sv.is_safe_for_optimization if sv else result["is_safe_for_optimization"],
        "checks": sv.checks if sv else result["checks"],
        "rejection_reasons": sv.rejection_reasons if sv else result["rejection_reasons"],
        "warnings": sv.warnings if sv else result["warnings"],
        "validated_by": sv.validated_by if sv else current_user.id,
        "validated_at": sv.validated_at.isoformat() if sv and sv.validated_at else datetime.now(timezone.utc).isoformat(),
        "planning_safety_status": cand.safety_status,
        "disclaimer": "Safety Engine validation only — does not approve block, does not select candidate, OR-Tools pending",
    }


@router.post("/revalidate/candidate/{candidate_id}")
def revalidate_candidate_endpoint(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot perform safety validation")
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role != "AUTHORIZED_OFFICIAL" and current_user.department_id != (mreq.department_id if mreq else None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    result = revalidate_candidate(candidate_id, db, user_id=current_user.id)
    return {
        "candidate_id": candidate_id,
        "block_request_id": cand.block_request_id,
        "overall_status": result["overall_status"],
        "is_safe_for_optimization": result["is_safe_for_optimization"],
        "checks": result["checks"],
        "rejection_reasons": result["rejection_reasons"],
        "warnings": result["warnings"],
        "validated_by": current_user.id,
        "planning_safety_status": cand.safety_status,
        "message": "Candidate revalidated against live operational state",
    }


@router.get("/safe-candidates/{block_request_id}")
def get_safe_candidates_endpoint(block_request_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_request_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER") and current_user.department_id != (mreq.department_id if mreq else None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    safe_cands = get_safe_candidates(block_request_id, db)
    return {
        "block_request_id": block_request_id,
        "total_safe_candidates": len(safe_cands),
        "safe_candidates": safe_cands,
    }


@router.get("/validations/candidate/{candidate_id}")
def get_validation(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER") and current_user.department_id != (mreq.department_id if mreq else None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == candidate_id).first()
    if not sv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No safety validation yet — run POST /validate/candidate/{id}")
    return {
        "candidate_id": sv.candidate_id,
        "block_request_id": sv.block_request_id,
        "overall_status": sv.overall_status,
        "is_safe_for_optimization": sv.is_safe_for_optimization,
        "checks": sv.checks,
        "rejection_reasons": sv.rejection_reasons,
        "warnings": sv.warnings,
        "validated_by": sv.validated_by,
        "validated_at": sv.validated_at.isoformat() if sv.validated_at else None,
        "planning_safety_status": cand.safety_status,
    }


@router.get("/validations/block/{block_id}")
def get_block_validations(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block_id).all()
    result = []
    for cand in cands:
        sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
        result.append({
            "candidate_id": cand.id,
            "candidate_start": cand.candidate_start.isoformat(),
            "candidate_end": cand.candidate_end.isoformat(),
            "planning_safety_status": cand.safety_status,
            "safety_validation": {
                "overall_status": sv.overall_status if sv else None,
                "is_safe_for_optimization": sv.is_safe_for_optimization if sv else None,
                "checks": sv.checks if sv else None,
                "rejection_reasons": sv.rejection_reasons if sv else None,
            } if sv else None,
            "validated": sv is not None,
            "is_selected": cand.is_selected,
            "optimization_score": float(cand.optimization_score) if cand.optimization_score else None,
        })
    return {"block_id": block_id, "total": len(result), "validations": result}


@router.get("/validations")
def list_validations(limit: int = 20, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Dept-scoped list
    q = db.query(SafetyValidation)
    # For non-privileged, filter to own dept via candidate's block's maintenance dept
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "EMERGENCY_OPERATOR"):
        # Join to filter
        q = q.join(BlockCandidate, SafetyValidation.candidate_id == BlockCandidate.id).join(BlockRequest, BlockCandidate.block_request_id == BlockRequest.id).join(MaintenanceRequest, BlockRequest.maintenance_request_id == MaintenanceRequest.id).filter(MaintenanceRequest.department_id == current_user.department_id)
    rows = q.order_by(SafetyValidation.validated_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "candidate_id": r.candidate_id,
            "block_request_id": r.block_request_id,
            "overall_status": r.overall_status,
            "is_safe_for_optimization": r.is_safe_for_optimization,
            "validated_by": r.validated_by,
            "validated_at": r.validated_at.isoformat() if r.validated_at else None,
        }
        for r in rows
    ]
