from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.block import BlockRequest, BlockCandidate, OptimizedBlock
from app.models.maintenance import MaintenanceRequest
from app.models.audit import AuditLog
from app.optimizer.engine import optimize_block_request, create_optimized_block

router = APIRouter(prefix="/api/optimization", tags=["optimization"])

ALLOWED_ROLES = {"ENGINEER_REVIEWER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}


def _audit(db: Session, user_id, action, entity_id=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="optimized_block", entity_id=entity_id, description=desc)
    db.add(log)
    db.commit()


@router.post("/blocks/{block_id}/optimize")
def optimize_block(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot optimize")
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role != "AUTHORIZED_OFFICIAL":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    # Run optimization — safety gate inside
    result = optimize_block_request(db, block_id, current_user.id)

    if result["status"] in ("NO_SAFE_CANDIDATES", "NO_FEASIBLE_SOLUTION", "FAILED"):
        _audit(db, current_user.id, "OPTIMIZATION_FAILED" if result["status"] != "NO_SAFE_CANDIDATES" else "OPTIMIZATION_NO_SAFE", entity_id=block_id, desc=f"{result['status']}: {result.get('reason')}")
        # Return 200 with status explanation, not 500 — no solution is not server error
        return {
            "block_request_id": block_id,
            "status": result["status"],
            "reason": result.get("reason"),
            "total_considered": result.get("total_considered"),
            "eligible": result.get("eligible"),
            "excluded": result.get("excluded"),
            "excluded_details": result.get("excluded_details", []),
            "optimization_score": None,
            "selected_candidate_id": None,
            "explanation": result.get("explanation") or result.get("reason"),
            "disclaimer": "No optimization — Safety Engine gate or CP-SAT found no feasible solution",
        }

    # Create optimized block
    try:
        ob = create_optimized_block(db, block_id, result, current_user.id)
    except Exception as e:
        _audit(db, current_user.id, "OPTIMIZATION_FAILED", entity_id=block_id, desc=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create optimized block: {e}")

    _audit(db, current_user.id, "OPTIMIZATION_COMPLETED", entity_id=ob.id, desc=f"Selected {result['selected_candidate_id']} score {result['optimization_score']} eligible {result['eligible']}")

    return {
        "block_request_id": block_id,
        "optimized_block_id": ob.id,
        "optimized_block_code": ob.block_code,
        "status": result["status"],
        "selected_candidate_id": result["selected_candidate_id"],
        "optimization_score": result["optimization_score"],
        "objective_value": result.get("objective_value"),
        "objective_summary": result.get("objective_summary"),
        "total_considered": result["total_considered"],
        "eligible": result["eligible"],
        "unsafe_excluded": result.get("unsafe_excluded"),
        "excluded_details": result.get("excluded_details"),
        "explanation": result["explanation"],
        "disclaimer": "Optimized recommendation only — requires Authorized Official approval, does not bypass safety",
        "combined_departments": ob.combined_departments,
    }


@router.get("/blocks/{block_id}")
def get_optimization(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    # Find latest optimized block for this block_request via optimized_block_sources
    from app.models.block import OptimizedBlockSource
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).order_by(OptimizedBlockSource.id.desc()).first()
    if not src:
        # Also check directly via block_id not in sources? Maybe no optimization yet
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No optimization yet for this block")
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "section_id": ob.section_id,
        "track_id": ob.track_id,
        "start_time": ob.start_time.isoformat() if ob.start_time else None,
        "end_time": ob.end_time.isoformat() if ob.end_time else None,
        "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
        "status": ob.status,
        "combined_departments": ob.combined_departments,
        "recommendation_reason": ob.recommendation_reason,
        "created_at": ob.created_at.isoformat() if ob.created_at else None,
    }


@router.get("/blocks/{block_id}/history")
def optimization_history(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    from app.models.block import OptimizedBlockSource
    srcs = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).order_by(OptimizedBlockSource.id.desc()).all()
    history = []
    for src in srcs:
        ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).first()
        if ob:
            history.append({
                "optimized_block_id": ob.id,
                "block_code": ob.block_code,
                "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
                "status": ob.status,
                "created_at": ob.created_at.isoformat() if ob.created_at else None,
            })
    return {"block_request_id": block_id, "total": len(history), "history": history}


@router.get("/candidates/{candidate_id}/safety")
def candidate_safety(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    from app.models.safety import SafetyValidation
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == candidate_id).first()
    if not sv:
        return {"candidate_id": candidate_id, "safety_validated": False, "reason": "No SafetyValidation — must validate via Safety Engine before optimization"}
    return {
        "candidate_id": candidate_id,
        "overall_status": sv.overall_status,
        "is_safe_for_optimization": sv.is_safe_for_optimization,
        "checks": sv.checks,
    }
