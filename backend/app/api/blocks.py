from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.maintenance import MaintenanceRequest
from app.models.block import BlockRequest, BlockCandidate
from app.models.audit import AuditLog
from app.schemas.block import BlockRequestCreate, BlockRequestOut, BlockRequestListResponse, CandidateOut, CandidateGenerateResponse

router = APIRouter(prefix="/api/blocks", tags=["blocks"])

# Only these maintenance statuses allow block planning
ALLOWED_MAINTENANCE_STATUSES = {"VERIFIED", "BLOCK_PLANNING", "AI_RECOMMENDATION"}

# Roles allowed to create block requests
BLOCK_CREATE_ROLES = {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}


def _audit(db: Session, user_id, action, entity_id=None, old=None, new=None, old_status=None, new_status=None, desc=None):
    actual_old = old_status if old_status is not None else old
    actual_new = new_status if new_status is not None else new
    is_block = "BLOCK" in action or "GENERATE_CANDIDATES" in action or "CREATE_BLOCK" in action or "CLEARANCE" in action or "EXECUTION" in action
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="block_request" if is_block else "block_candidate",
        entity_id=entity_id,
        old_status=actual_old,
        new_status=actual_new,
        description=desc,
    )
    db.add(log)
    db.commit()


def _gen_block_code(db: Session):
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    cnt = db.query(BlockRequest).count() + 1
    return f"BLK-{today}-{cnt:04d}"


def _to_block_out(b: BlockRequest) -> BlockRequestOut:
    duration = None
    if b.requested_start and b.requested_end:
        duration = int((b.requested_end - b.requested_start).total_seconds() // 60)
    return BlockRequestOut(
        id=b.id,
        block_code=b.block_code,
        maintenance_request_id=b.maintenance_request_id,
        section_id=b.section_id,
        track_id=b.track_id,
        requested_start=b.requested_start,
        requested_end=b.requested_end,
        duration_mins=duration,
        block_type=b.block_type,
        status=b.status,
        created_at=b.created_at,
    )


def _to_candidate_out(c: BlockCandidate) -> CandidateOut:
    return CandidateOut(
        id=c.id,
        block_request_id=c.block_request_id,
        section_id=c.section_id,
        track_id=c.track_id,
        candidate_start=c.candidate_start,
        candidate_end=c.candidate_end,
        predicted_duration_mins=c.predicted_duration_mins,
        predicted_delay_mins=c.predicted_delay_mins,
        asset_risk_score=float(c.asset_risk_score) if c.asset_risk_score is not None else None,
        safety_status=c.safety_status,
        safety_rejection_reason=c.safety_rejection_reason,
        optimization_score=float(c.optimization_score) if c.optimization_score is not None else None,
        is_selected=c.is_selected,
        created_at=c.created_at,
    )


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


@router.post("/requests", response_model=BlockRequestOut, status_code=status.HTTP_201_CREATED)
def create_block_request(payload: BlockRequestCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in BLOCK_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role {current_user.role} cannot create block requests")
    if payload.requested_end <= payload.requested_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="requested_end must be after requested_start")

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == payload.maintenance_request_id).first()
    if not mreq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
    if mreq.status not in ALLOWED_MAINTENANCE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Maintenance request status {mreq.status} does not allow block planning. Required {ALLOWED_MAINTENANCE_STATUSES}")
    # Department ownership: block's section/track must match maintenance's section/track? Enforce same section/track
    # If payload had section/track they would be validated, but client doesn't send — derive from maintenance request
    section_id = mreq.section_id
    track_id = mreq.track_id
    # Duration check: requested window should at least cover maintenance duration if known
    if mreq.requested_duration_mins:
        minutes = int((payload.requested_end - payload.requested_start).total_seconds() // 60)
        if minutes < mreq.requested_duration_mins:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Block window {minutes} mins shorter than maintenance requested {mreq.requested_duration_mins} mins")
    # Check existing block conflict at planning-data level: overlapping block on same section/track
    # Query block_requests where same section/track and overlapping window and status not cancelled/rejected/completed
    conflicting = db.query(BlockRequest).filter(
        BlockRequest.section_id == section_id,
        BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        BlockRequest.requested_start < payload.requested_end,
        BlockRequest.requested_end > payload.requested_start,
    )
    if track_id:
        conflicting = conflicting.filter((BlockRequest.track_id == track_id) | (BlockRequest.track_id.is_(None)))
    # Note: we allow creation but will flag candidate later; for request creation we just warn via header? For now allow but audit
    has_conflict = conflicting.first() is not None

    # Also check optimized_blocks overlapping
    from app.models.block import OptimizedBlock

    opt_conflict = db.query(OptimizedBlock).filter(
        OptimizedBlock.section_id == section_id,
        OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        OptimizedBlock.start_time < payload.requested_end,
        OptimizedBlock.end_time > payload.requested_start,
    ).first()
    if track_id and opt_conflict and opt_conflict.track_id and opt_conflict.track_id != track_id:
        opt_conflict = None  # different track, no conflict
    if opt_conflict:
        has_conflict = True

    code = _gen_block_code(db)
    block = BlockRequest(
        block_code=code,
        maintenance_request_id=mreq.id,
        section_id=section_id,
        track_id=track_id,
        requested_start=payload.requested_start,
        requested_end=payload.requested_end,
        block_type=payload.block_type,
        status="REQUESTED",
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    desc = f"Created {code} for maintenance {mreq.request_code}"
    if has_conflict:
        desc += " — planning conflict exists (existing block overlapping, candidate generation will mark INFEASIBLE where applicable)"
    _audit(db, current_user.id, "CREATE_BLOCK", entity_id=block.id, old=None, new="REQUESTED", desc=desc)
    return _to_block_out(block)


@router.get("/requests", response_model=BlockRequestListResponse)
def list_block_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(BlockRequest).join(MaintenanceRequest, BlockRequest.maintenance_request_id == MaintenanceRequest.id)
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "EMERGENCY_OPERATOR")
    if not is_privileged:
        query = query.filter(MaintenanceRequest.department_id == current_user.department_id)
    if status:
        query = query.filter(BlockRequest.status == status)
    total = query.count()
    items = query.order_by(BlockRequest.id.desc()).offset(skip).limit(limit).all()
    return BlockRequestListResponse(total=total, items=[_to_block_out(b) for b in items], skip=skip, limit=limit)


@router.get("/requests/{block_id}", response_model=BlockRequestOut)
def get_block_request(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return _to_block_out(block)


from app.services.candidate_generator import CandidateGeneratorService
from app.safety.engine import get_safe_candidates, validate_candidate, revalidate_candidate

candidate_generator = CandidateGeneratorService()


@router.post("/requests/{block_id}/candidates/generate", response_model=CandidateGenerateResponse)
def generate_candidates(block_id: int, payload: dict | None = None, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in BLOCK_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot generate candidates")
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    body = payload or {}
    interval_mins = int(body.get("interval_minutes") or body.get("granularity_mins") or 30)
    max_cand = int(body.get("max_candidates") or 5)
    buffer_mins = int(body.get("min_duration_buffer_mins") or 0)
    window_days = int(body.get("candidate_window_days") or 1)

    try:
        gen_res = candidate_generator.generate_candidates_for_block(
            db=db,
            block_request_id=block_id,
            user_id=current_user.id,
            interval_mins=interval_mins,
            max_candidates=max_cand,
            min_duration_buffer_mins=buffer_mins,
            window_days=window_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # Fetch persisted candidates for response
    candidates = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block_id).order_by(BlockCandidate.candidate_start.asc()).all()
    outs = [_to_candidate_out(c) for c in candidates]

    return CandidateGenerateResponse(
        generated=len(outs),
        safe_candidates_count=gen_res["safe_candidates_count"],
        unsafe_candidates_count=gen_res["unsafe_candidates_count"],
        candidates=outs,
        message=gen_res["message"],
    )


@router.get("/requests/{block_id}/candidates", response_model=list[CandidateOut])
def list_candidates(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block_id).order_by(BlockCandidate.candidate_start).all()
    return [_to_candidate_out(c) for c in cands]


@router.get("/requests/{block_id}/candidates/safe")
def list_safe_candidates(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return get_safe_candidates(block_id, db)


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return _to_candidate_out(cand)


@router.post("/candidates/{candidate_id}/revalidate")
def revalidate_candidate_endpoint(candidate_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in BLOCK_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot revalidate candidates")
    cand = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    block = db.query(BlockRequest).filter(BlockRequest.id == cand.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    result = revalidate_candidate(candidate_id, db, user_id=current_user.id)
    return result


# ============================================================
# PHASE 8 BLOCK LIFECYCLE & EXECUTION STATE MACHINE
# ============================================================

from app.models.block import OptimizedBlock, OptimizedBlockSource, BlockResourceAllocation
from app.models.notification import Notification


class BlockActionPayload(dict):
    pass


@router.get("/scheduled")
def list_scheduled_blocks(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    obs = db.query(OptimizedBlock).filter(OptimizedBlock.status.in_(["SCHEDULED", "APPROVED"])).order_by(OptimizedBlock.start_time.asc()).all()
    results = []
    for ob in obs:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first() if blk else None
        results.append({
            "optimized_block_id": ob.id,
            "block_code": ob.block_code,
            "section_id": ob.section_id,
            "track_id": ob.track_id,
            "start_time": ob.start_time.isoformat() if ob.start_time else None,
            "end_time": ob.end_time.isoformat() if ob.end_time else None,
            "duration_mins": ob.total_duration_mins,
            "status": ob.status,
            "approved_by": ob.approved_by,
            "approved_at": ob.approved_at.isoformat() if ob.approved_at else None,
            "department": mreq.department_id if mreq else None,
        })
    return results


@router.get("/active")
def list_active_blocks(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    obs = db.query(OptimizedBlock).filter(OptimizedBlock.status.in_(["ACTIVE", "MAINTENANCE", "CLEARANCE_PENDING"])).order_by(OptimizedBlock.start_time.asc()).all()
    results = []
    for ob in obs:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first() if blk else None
        results.append({
            "optimized_block_id": ob.id,
            "block_code": ob.block_code,
            "section_id": ob.section_id,
            "track_id": ob.track_id,
            "start_time": ob.start_time.isoformat() if ob.start_time else None,
            "end_time": ob.end_time.isoformat() if ob.end_time else None,
            "duration_mins": ob.total_duration_mins,
            "status": ob.status,
            "approved_by": ob.approved_by,
            "department": mreq.department_id if mreq else None,
        })
    return results


@router.post("/{block_id}/activate")
def activate_block(
    block_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "SENIOR_SECTION_ENGINEER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot activate blocks")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == block_id).with_for_update().first()
    if not ob:
        # Check if block_id is a block_request id
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).first()
        if src:
            ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).with_for_update().first()

    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    # Strict state transition: Must be SCHEDULED or APPROVED
    if ob.status not in ("SCHEDULED", "APPROVED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: Cannot activate block in status '{ob.status}'. Must be SCHEDULED or APPROVED."
        )

    previous_status = ob.status
    ob.status = "ACTIVE"
    now_utc = datetime.now(timezone.utc)

    # Update source and maintenance requests
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        if blk:
            blk.status = "ACTIVE"
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()
            if mreq:
                mreq.status = "IN_PROGRESS"

    db.commit()
    db.refresh(ob)

    body = payload or {}
    is_simulation = body.get("simulation", True)
    mode_label = "SIMULATION / DEMO ACTIVATION" if is_simulation else "OPERATIONAL ACTIVATION"

    _audit(
        db=db,
        user_id=current_user.id,
        action="EXECUTION_START",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="ACTIVE",
        desc=f"Block {ob.block_code} activated ({mode_label}) by {current_user.name}.",
    )

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "previous_status": previous_status,
        "status": ob.status,
        "activated_by": current_user.id,
        "activated_at": now_utc.isoformat(),
        "mode": mode_label,
        "message": f"Block {ob.block_code} is now ACTIVE ({mode_label}). Track/section isolation is marked in decision-support state.",
    }


@router.post("/{block_id}/maintenance")
def set_maintenance_state(
    block_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "SENIOR_SECTION_ENGINEER", "JUNIOR_ENGINEER", "MAINTENANCE_STAFF"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot update maintenance status")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == block_id).with_for_update().first()
    if not ob:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).first()
        if src:
            ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    if ob.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: Cannot enter MAINTENANCE from status '{ob.status}'. Must be ACTIVE."
        )

    previous_status = ob.status
    ob.status = "MAINTENANCE"
    db.commit()
    db.refresh(ob)

    _audit(
        db=db,
        user_id=current_user.id,
        action="MAINTENANCE_IN_PROGRESS",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="MAINTENANCE",
        desc=f"Maintenance work actively in progress for block {ob.block_code}.",
    )

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "message": f"Block {ob.block_code} marked as MAINTENANCE in progress.",
    }


@router.post("/{block_id}/clearance")
def request_clearance(
    block_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "SENIOR_SECTION_ENGINEER", "JUNIOR_ENGINEER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot request clearance")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == block_id).with_for_update().first()
    if not ob:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).first()
        if src:
            ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    if ob.status not in ("ACTIVE", "MAINTENANCE"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: Cannot request clearance from status '{ob.status}'. Must be ACTIVE or MAINTENANCE."
        )

    previous_status = ob.status
    ob.status = "CLEARANCE_PENDING"
    db.commit()
    db.refresh(ob)

    _audit(
        db=db,
        user_id=current_user.id,
        action="CLEARANCE_REQUESTED",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="CLEARANCE_PENDING",
        desc=f"Safety and track clearance requested for block {ob.block_code}.",
    )

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "message": f"Block {ob.block_code} is now in CLEARANCE_PENDING state. Track inspection and clearance check required before release.",
    }


@router.post("/{block_id}/release")
def release_block(
    block_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Authorized Official or Controller can release blocks")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == block_id).with_for_update().first()
    if not ob:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).first()
        if src:
            ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    # Strict clearance requirement: cannot jump directly from ACTIVE to RELEASED without CLEARANCE_PENDING
    if ob.status != "CLEARANCE_PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: Cannot release block in status '{ob.status}'. Clearance check is mandatory (must be CLEARANCE_PENDING)."
        )

    previous_status = ob.status
    ob.status = "RELEASED"

    # Release any allocated resources
    allocs = db.query(BlockResourceAllocation).filter(BlockResourceAllocation.block_id == ob.id, BlockResourceAllocation.status == "ALLOCATED").all()
    for al in allocs:
        al.status = "RELEASED"

    db.commit()
    db.refresh(ob)

    _audit(
        db=db,
        user_id=current_user.id,
        action="CLEARANCE_GRANTED",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="RELEASED",
        desc=f"Block {ob.block_code} cleared and RELEASED by {current_user.name}.",
    )

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "message": f"Block {ob.block_code} successfully released. Track is cleared for normal train traffic.",
    }


@router.post("/{block_id}/complete")
def complete_block(
    block_id: int,
    payload: Optional[dict] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "SENIOR_SECTION_ENGINEER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot complete blocks")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == block_id).with_for_update().first()
    if not ob:
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == block_id).first()
        if src:
            ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")

    if ob.status not in ("RELEASED", "ACTIVE", "CLEARANCE_PENDING"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete block from status '{ob.status}'."
        )

    previous_status = ob.status
    ob.status = "COMPLETED"

    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        if blk:
            blk.status = "COMPLETED"
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()
            if mreq:
                mreq.status = "COMPLETED"

    # Release any lingering resources
    allocs = db.query(BlockResourceAllocation).filter(BlockResourceAllocation.block_id == ob.id, BlockResourceAllocation.status == "ALLOCATED").all()
    for al in allocs:
        al.status = "RELEASED"

    db.commit()
    db.refresh(ob)

    _audit(
        db=db,
        user_id=current_user.id,
        action="EXECUTION_COMPLETE",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="COMPLETED",
        desc=f"Block {ob.block_code} completed and closed.",
    )

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "message": f"Block {ob.block_code} execution lifecycle is completed.",
    }


