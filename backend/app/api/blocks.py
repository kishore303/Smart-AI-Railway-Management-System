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
BLOCK_CREATE_ROLES = {"ENGINEER_REVIEWER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}


def _audit(db: Session, user_id, action, entity_id=None, old=None, new=None, desc=None):
    # GENERATE_CANDIDATES is about block_request, not candidate row
    is_block = "BLOCK" in action or "GENERATE_CANDIDATES" in action or "CREATE_BLOCK" in action
    log = AuditLog(user_id=user_id, action=action, entity_type="block_request" if is_block else "block_candidate", entity_id=entity_id, old_status=old, new_status=new, description=desc)
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

    # Clear old candidates for this block (if regenerating)
    existing = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block_id).count()
    # Generate 3 candidates: requested, +24h, +48h (or -24h if future far). For deterministic tests, use requested +0, +24h, +48h
    duration = int((block.requested_end - block.requested_start).total_seconds() // 60)
    # Fetch predicted duration if available from maintenance_predictions
    from app.models.maintenance import MaintenancePrediction

    pred = db.query(MaintenancePrediction).filter(MaintenancePrediction.maintenance_request_id == mreq.id).order_by(MaintenancePrediction.predicted_at.desc()).first()
    if pred and pred.predicted_duration_mins:
        pred_duration = pred.predicted_duration_mins
        pred_delay = pred.predicted_delay_mins
        pred_risk = pred.asset_risk_score
    else:
        pred_duration = duration
        pred_delay = None
        pred_risk = None

    candidates = []
    base_start = block.requested_start
    # Honor frontend controls when provided: max_candidates (1-10), 24h spacing.
    # candidate_window_days / min_duration_buffer_mins accepted for forward-compat.
    try:
        requested_max = int((payload or {}).get("max_candidates", 3))
    except (TypeError, ValueError):
        requested_max = 3
    max_candidates = max(1, min(10, requested_max))
    # Ensure timezone aware
    for idx in range(max_candidates):
        offset_hours = idx * 24
        cand_start = base_start + timedelta(hours=offset_hours)
        cand_end = cand_start + timedelta(minutes=duration)
        # Planning-level conflict detection: check overlapping existing blocks/candidates on same section/track
        # Check block_requests overlapping
        conflict = db.query(BlockRequest).filter(
            BlockRequest.id != block.id,
            BlockRequest.section_id == block.section_id,
            BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            BlockRequest.requested_start < cand_end,
            BlockRequest.requested_end > cand_start,
        )
        if block.track_id:
            conflict = conflict.filter((BlockRequest.track_id == block.track_id) | (BlockRequest.track_id.is_(None)))
        has_conflict = conflict.first() is not None
        # Check optimized_blocks
        from app.models.block import OptimizedBlock

        opt = db.query(OptimizedBlock).filter(
            OptimizedBlock.section_id == block.section_id,
            OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            OptimizedBlock.start_time < cand_end,
            OptimizedBlock.end_time > cand_start,
        )
        if block.track_id:
            # only conflict if same track or optimized has null track (section-level)
            opt = opt.filter((OptimizedBlock.track_id == block.track_id) | (OptimizedBlock.track_id.is_(None)))
        if opt.first() is not None:
            has_conflict = True

        # Do NOT claim safety — mark planning conflict as INFEASIBLE with clear reason, otherwise FEASIBLE with disclaimer that Safety Engine pending
        if has_conflict:
            safety_status = "INFEASIBLE"
            reason = "Planning-level conflict: overlapping existing block on same section/track (Safety Engine validation still required)"
        else:
            safety_status = "FEASIBLE"
            reason = None  # keep null; Safety Engine will still validate

        # Note: we add disclaimer via reason? For feasible, keep null but API returns disclaimer not to trust safety yet
        cand = BlockCandidate(
            block_request_id=block.id,
            section_id=block.section_id,
            track_id=block.track_id,
            candidate_start=cand_start,
            candidate_end=cand_end,
            predicted_duration_mins=pred_duration,
            predicted_delay_mins=pred_delay,
            asset_risk_score=pred_risk,
            safety_status=safety_status,
            safety_rejection_reason=reason,
            optimization_score=None,  # OR-Tools not yet
            is_selected=False,
        )
        db.add(cand)
        candidates.append(cand)

    db.commit()
    for c in candidates:
        db.refresh(c)
    # Audit
    _audit(db, current_user.id, "GENERATE_CANDIDATES", entity_id=block.id, old=None, new=None, desc=f"Generated {len(candidates)} candidates for {block.block_code}")

    outs = [_to_candidate_out(c) for c in candidates]
    msg = "Candidates generated at planning level only — Safety Engine validation and OR-Tools optimization still required before approval. Do NOT treat FEASIBLE as safe."
    return CandidateGenerateResponse(generated=len(outs), candidates=outs, message=msg)


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
