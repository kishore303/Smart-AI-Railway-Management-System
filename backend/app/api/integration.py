from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from typing import Optional, List

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.block import BlockRequest, BlockIntegrationRequest
from app.models.maintenance import MaintenanceRequest
from app.models.asset import Asset
from app.models.railway import RailwaySection, Track
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationOut,
    IntegrationListResponse,
    IntegrationRespond,
    IntegrationModify,
    JoinBlockRequest,
    OpportunityDetectRequest,
    OpportunityDetectResponse,
    IntegrationCancelResponse,
)

router = APIRouter(prefix="/api/integration", tags=["integration"])

# Roles allowed to create/respond
INTEGRATION_CREATE_ROLES = {"MAINTENANCE_STAFF", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}
INTEGRATION_RESPOND_ROLES = {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "CONTROLLER", "AUTHORIZED_OFFICIAL", "MAINTENANCE_STAFF"}


def _audit(db: Session, user_id, action, entity_id=None, old=None, new=None, desc=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="block_integration_request",
        entity_id=entity_id,
        old_status=old,
        new_status=new,
        description=desc,
    )
    db.add(log)
    db.commit()


def _notify(
    db: Session,
    recipient_dept_id: Optional[int] = None,
    recipient_user_id: Optional[int] = None,
    type_: str = "BLOCK_INTEGRATION_OPPORTUNITY",
    title: str = "Integration Notification",
    message: Optional[str] = None,
    integration_id: Optional[int] = None,
    priority: str = "NORMAL",
):
    try:
        n = Notification(
            recipient_department_id=recipient_dept_id,
            recipient_user_id=recipient_user_id,
            type=type_,
            title=title,
            message=message,
            priority=priority,
            integration_request_id=integration_id,
        )
        db.add(n)
        db.commit()
    except Exception:
        db.rollback()


def _get_block(db: Session, block_id: int) -> BlockRequest:
    b = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Block {block_id} not found")
    return b


def _get_block_dept(db: Session, block_id: int) -> int:
    block = _get_block(db, block_id)
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance for block not found")
    return mreq.department_id


def _compute_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime):
    latest_start = max(a_start, b_start)
    earliest_end = min(a_end, b_end)
    if latest_start >= earliest_end:
        return 0, None, None
    duration_mins = int((earliest_end - latest_start).total_seconds() // 60)
    return duration_mins, latest_start, earliest_end


def _assess_spatial_and_compatibility(
    db: Session,
    src_block: BlockRequest,
    tgt_block: BlockRequest,
    overlap_mins: int,
):
    # Retrieve maintenance details for asset/location checking
    m_src = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == src_block.maintenance_request_id).first()
    m_tgt = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == tgt_block.maintenance_request_id).first()

    same_section = src_block.section_id == tgt_block.section_id
    same_track = (src_block.track_id is not None) and (src_block.track_id == tgt_block.track_id)

    # Spatial status check
    spatial_status = "SAME_SECTION"
    if same_section and same_track:
        spatial_status = "SAME_TRACK"
    elif same_section and not same_track:
        spatial_status = "ADJACENT_OR_DIFFERENT_TRACK"
    elif not same_section:
        spatial_status = "DIFFERENT_SECTION"

    # Missing location check
    if not src_block.section_id or not tgt_block.section_id or (m_src and not m_src.asset_id) or (m_tgt and not m_tgt.asset_id):
        return "INSUFFICIENT_DATA", spatial_status, 20.0, "Location or asset data is incomplete."

    # Compatibility determination
    if same_section and same_track and overlap_mins > 0:
        compat = "COMPATIBLE" if overlap_mins >= 30 else "POTENTIAL_COMPATIBLE"
        reason = f"Same section and track ({src_block.section_id}/T{src_block.track_id}) with {overlap_mins}m window overlap."
        score = min(95.0, 50.0 + (overlap_mins / 2.0) + (15.0 if same_track else 0.0))
    elif same_section and not same_track and overlap_mins > 0:
        compat = "REQUIRES_SAFETY_VALIDATION"
        reason = f"Same section ({src_block.section_id}) on adjacent/different tracks with {overlap_mins}m overlap. Potential adjacent-line interaction requires Safety Engine check."
        score = 60.0
    elif same_section and overlap_mins == 0:
        compat = "POTENTIALLY_COMPATIBLE"
        reason = f"Same section ({src_block.section_id}) with adjacent or sequential time windows."
        score = 45.0
    else:
        compat = "REQUIRES_SAFETY_VALIDATION"
        reason = "Different section coordinates require full cross-department corridor safety review."
        score = 30.0

    return compat, spatial_status, round(score, 2), reason


def _to_out(req: BlockIntegrationRequest, db: Session) -> IntegrationOut:
    req_dept = db.query(Department).filter(Department.id == req.requesting_department_id).first()
    tgt_dept = db.query(Department).filter(Department.id == req.target_department_id).first()
    src_block = db.query(BlockRequest).filter(BlockRequest.id == req.source_block_id).first()
    tgt_block = db.query(BlockRequest).filter(BlockRequest.id == req.target_block_id).first()

    return IntegrationOut(
        id=req.id,
        source_block_id=req.source_block_id,
        target_block_id=req.target_block_id,
        source_block_code=src_block.block_code if src_block else None,
        target_block_code=tgt_block.block_code if tgt_block else None,
        requesting_department_id=req.requesting_department_id,
        requesting_department_code=req_dept.code if req_dept else "UNKNOWN",
        target_department_id=req.target_department_id,
        target_department_code=tgt_dept.code if tgt_dept else "UNKNOWN",
        section_id=req.section_id or (src_block.section_id if src_block else None),
        track_id=req.track_id or (src_block.track_id if src_block else None),
        overlap_start=req.overlap_start,
        overlap_end=req.overlap_end,
        overlap_duration_mins=req.overlap_duration_mins,
        coordination_score=float(req.coordination_score) if req.coordination_score is not None else None,
        detection_reason=req.detection_reason,
        spatial_status=req.spatial_status,
        compatibility_status=req.compatibility_status,
        requested_by=req.requested_by,
        response_by=req.response_by,
        response=req.response,
        reason=req.reason,
        modified_start=req.modified_start,
        modified_end=req.modified_end,
        final_status=req.final_status,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


# ==================== Coordination Detection Engine ====================

@router.post("/detect", response_model=OpportunityDetectResponse)
def detect_opportunities(
    payload: Optional[OpportunityDetectRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Deterministic Coordination Detector:
    Scans verified block requests across distinct departments in the same section with overlapping windows,
    computes preliminary compatibility, and records opportunities idempotently.
    """
    query = db.query(BlockRequest).filter(BlockRequest.status.in_(["REQUESTED", "PROPOSED", "UNDER_REVIEW"]))
    if payload and payload.section_id:
        query = query.filter(BlockRequest.section_id == payload.section_id)

    blocks = query.all()
    detected: List[BlockIntegrationRequest] = []

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            b1 = blocks[i]
            b2 = blocks[j]

            dept1 = _get_block_dept(db, b1.id)
            dept2 = _get_block_dept(db, b2.id)

            # Different departments only
            if dept1 == dept2:
                continue

            # Check time overlap
            overlap_mins, o_start, o_end = _compute_overlap(b1.requested_start, b1.requested_end, b2.requested_start, b2.requested_end)
            if overlap_mins <= 0 and b1.section_id != b2.section_id:
                continue

            # Idempotency check: see if active integration exists for this pair
            existing = db.query(BlockIntegrationRequest).filter(
                ((BlockIntegrationRequest.source_block_id == b1.id) & (BlockIntegrationRequest.target_block_id == b2.id))
                | ((BlockIntegrationRequest.source_block_id == b2.id) & (BlockIntegrationRequest.target_block_id == b1.id)),
                BlockIntegrationRequest.final_status.in_(["PENDING", "ACCEPTED", "MODIFIED"]),
            ).first()

            if existing:
                detected.append(existing)
                continue

            compat, spatial_stat, score, reason = _assess_spatial_and_compatibility(db, b1, b2, overlap_mins)

            req = BlockIntegrationRequest(
                source_block_id=b1.id,
                target_block_id=b2.id,
                requesting_department_id=dept1,
                target_department_id=dept2,
                section_id=b1.section_id,
                track_id=b1.track_id if b1.track_id == b2.track_id else None,
                overlap_start=o_start,
                overlap_end=o_end,
                overlap_duration_mins=overlap_mins if overlap_mins > 0 else None,
                coordination_score=score,
                detection_reason=reason,
                spatial_status=spatial_stat,
                compatibility_status=compat,
                requested_by=current_user.id,
                final_status="PENDING",
            )
            db.add(req)
            db.commit()
            db.refresh(req)

            _audit(db, current_user.id, "COORDINATION_DETECTED", entity_id=req.id, old=None, new="PENDING", desc=reason)
            _notify(
                db,
                recipient_dept_id=dept2,
                type_="BLOCK_INTEGRATION_OPPORTUNITY",
                title=f"Coordination Opportunity: {b1.block_code} ↔ {b2.block_code}",
                message=reason,
                integration_id=req.id,
                priority="HIGH" if compat == "COMPATIBLE" else "NORMAL",
            )
            detected.append(req)

    out = [_to_out(item, db) for item in detected]
    return OpportunityDetectResponse(detected_count=len(out), opportunities=out)


# ==================== Core Integration Endpoints ====================

@router.get("/opportunities", response_model=IntegrationListResponse)
@router.get("/requests", response_model=IntegrationListResponse)
def list_integrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    section_id: Optional[int] = Query(None),
    department_code: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER")
    query = db.query(BlockIntegrationRequest)

    if not is_privileged:
        query = query.filter(
            (BlockIntegrationRequest.requesting_department_id == current_user.department_id)
            | (BlockIntegrationRequest.target_department_id == current_user.department_id)
        )
    if status:
        query = query.filter(BlockIntegrationRequest.final_status == status)
    if section_id:
        query = query.filter(BlockIntegrationRequest.section_id == section_id)
    if department_code:
        dept = db.query(Department).filter(Department.code == department_code).first()
        if dept:
            query = query.filter(
                (BlockIntegrationRequest.requesting_department_id == dept.id)
                | (BlockIntegrationRequest.target_department_id == dept.id)
            )

    total = query.count()
    items = query.order_by(BlockIntegrationRequest.id.desc()).offset(skip).limit(limit).all()
    return IntegrationListResponse(total=total, items=[_to_out(i, db) for i in items], skip=skip, limit=limit)


@router.get("/opportunities/{integration_id}", response_model=IntegrationOut)
@router.get("/requests/{integration_id}", response_model=IntegrationOut)
def get_integration(integration_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration opportunity not found")
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER")
    if not is_privileged and current_user.department_id not in (req.requesting_department_id, req.target_department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return _to_out(req, db)


@router.post("/requests", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(payload: IntegrationCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in INTEGRATION_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot create integration request")
    if payload.source_block_id == payload.target_block_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Source and target must differ")

    src = _get_block(db, payload.source_block_id)
    tgt = _get_block(db, payload.target_block_id)
    src_dept = _get_block_dept(db, payload.source_block_id)
    tgt_dept = _get_block_dept(db, payload.target_block_id)

    if src_dept == tgt_dept:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cross-department integration requires different departments")
    if current_user.department_id != src_dept and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester must belong to source block's department")

    # Check duplicate active PENDING
    existing = db.query(BlockIntegrationRequest).filter(
        ((BlockIntegrationRequest.source_block_id == payload.source_block_id) & (BlockIntegrationRequest.target_block_id == payload.target_block_id))
        | ((BlockIntegrationRequest.source_block_id == payload.target_block_id) & (BlockIntegrationRequest.target_block_id == payload.source_block_id)),
        BlockIntegrationRequest.final_status == "PENDING",
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active pending integration request already exists for this pair")

    overlap_mins, o_start, o_end = _compute_overlap(src.requested_start, src.requested_end, tgt.requested_start, tgt.requested_end)
    compat, spatial_stat, score, reason = _assess_spatial_and_compatibility(db, src, tgt, overlap_mins)

    req = BlockIntegrationRequest(
        source_block_id=payload.source_block_id,
        target_block_id=payload.target_block_id,
        requesting_department_id=src_dept,
        target_department_id=tgt_dept,
        section_id=src.section_id,
        track_id=src.track_id if src.track_id == tgt.track_id else None,
        overlap_start=o_start,
        overlap_end=o_end,
        overlap_duration_mins=overlap_mins if overlap_mins > 0 else None,
        coordination_score=score,
        detection_reason=reason,
        spatial_status=spatial_stat,
        compatibility_status=compat,
        requested_by=current_user.id,
        final_status="PENDING",
        reason=payload.reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    _audit(db, current_user.id, "REQUEST_INTEGRATION", entity_id=req.id, old=None, new="PENDING", desc=f"{src_dept}->{tgt_dept} compat={compat}")
    _notify(
        db,
        recipient_dept_id=tgt_dept,
        type_="BLOCK_INTEGRATION_OPPORTUNITY",
        title=f"Integration request from Dept {src_dept}",
        message=f"Block {src.block_code} proposes integration with {tgt.block_code}. {payload.reason or reason}",
        integration_id=req.id,
    )
    return _to_out(req, db)


@router.post("/requests/{integration_id}/respond", response_model=IntegrationOut)
def respond_integration(integration_id: int, payload: IntegrationRespond, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in INTEGRATION_RESPOND_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot respond to integration")
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if req.final_status != "PENDING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot respond to {req.final_status} request")
    if current_user.department_id != req.target_department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only target department can respond")
    if current_user.id == req.requested_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester cannot respond to own integration")

    resp = payload.response.strip().upper()
    if resp not in ("ACCEPT", "REJECT", "MODIFY"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Response must be ACCEPT, REJECT, or MODIFY")
    if resp == "REJECT" and (not payload.reason or not payload.reason.strip()):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rejection reason is mandatory")

    mapping = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "MODIFY": "MODIFIED"}
    old = req.final_status
    req.response = resp
    req.response_by = current_user.id
    req.reason = payload.reason.strip() if payload.reason else req.reason
    if payload.modified_start:
        req.modified_start = payload.modified_start
    if payload.modified_end:
        req.modified_end = payload.modified_end
    req.final_status = mapping[resp]
    db.commit()
    db.refresh(req)

    audit_action = {"ACCEPT": "ACCEPT_INTEGRATION", "REJECT": "REJECT_INTEGRATION", "MODIFY": "MODIFY_INTEGRATION"}[resp]
    _audit(db, current_user.id, audit_action, entity_id=req.id, old=old, new=req.final_status, desc=payload.reason)
    ntype = {"ACCEPT": "INTEGRATION_ACCEPTED", "REJECT": "INTEGRATION_REJECTED", "MODIFY": "BLOCK_INTEGRATION_OPPORTUNITY"}[resp]
    _notify(
        db,
        recipient_dept_id=req.requesting_department_id,
        recipient_user_id=req.requested_by,
        type_=ntype,
        title=f"Integration {resp} by Target Department",
        message=f"Request {req.id} {resp}: {payload.reason or 'Agreed to coordinate.'}",
        integration_id=req.id,
    )
    return _to_out(req, db)


@router.post("/opportunities/{integration_id}/accept", response_model=IntegrationOut)
@router.post("/requests/{integration_id}/accept", response_model=IntegrationOut)
def accept_integration(integration_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return respond_integration(integration_id, IntegrationRespond(response="ACCEPT", reason="Department accepted coordination opportunity."), current_user, db)


@router.post("/opportunities/{integration_id}/reject", response_model=IntegrationOut)
@router.post("/requests/{integration_id}/reject", response_model=IntegrationOut)
def reject_integration(integration_id: int, payload: IntegrationRespond, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rejection reason is mandatory")
    payload.response = "REJECT"
    return respond_integration(integration_id, payload, current_user, db)


@router.post("/opportunities/{integration_id}/modify", response_model=IntegrationOut)
@router.post("/requests/{integration_id}/modify", response_model=IntegrationOut)
def modify_integration(integration_id: int, payload: IntegrationModify, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    respond_payload = IntegrationRespond(
        response="MODIFY",
        reason=payload.reason,
        modified_start=payload.modified_start,
        modified_end=payload.modified_end,
    )
    return respond_integration(integration_id, respond_payload, current_user, db)


@router.post("/requests/{integration_id}/cancel", response_model=IntegrationOut)
def cancel_integration(integration_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if req.final_status != "PENDING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only PENDING requests can be cancelled")
    if current_user.id != req.requested_by and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requester or official can cancel")

    old = req.final_status
    req.final_status = "REJECTED"
    req.response = "REJECT"
    req.response_by = current_user.id
    db.commit()
    db.refresh(req)
    _audit(db, current_user.id, "CANCEL_INTEGRATION", entity_id=req.id, old=old, new="REJECTED", desc="Cancelled by requester")
    return _to_out(req, db)


@router.post("/requests/join-block", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def request_to_join_block(payload: JoinBlockRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Request to join an existing block requirement.
    Creates an integration proposal between an existing block and a verified maintenance request.
    """
    target_block = _get_block(db, payload.block_id)
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == payload.maintenance_request_id).first()
    if not mreq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
    if mreq.status not in ("VERIFIED", "BLOCK_PLANNING"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only VERIFIED maintenance requests can join blocks")

    # Find or create source block request for this maintenance request
    src_block = db.query(BlockRequest).filter(BlockRequest.maintenance_request_id == mreq.id).first()
    if not src_block:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        cnt = db.query(BlockRequest).count() + 1
        src_block = BlockRequest(
            block_code=f"BLK-{today}-{cnt:04d}",
            maintenance_request_id=mreq.id,
            section_id=mreq.section_id,
            track_id=mreq.track_id,
            requested_start=mreq.requested_start,
            requested_end=mreq.requested_end,
            block_type=mreq.maintenance_type,
            status="REQUESTED",
        )
        db.add(src_block)
        db.commit()
        db.refresh(src_block)

    create_payload = IntegrationCreate(
        source_block_id=src_block.id,
        target_block_id=target_block.id,
        reason=payload.reason or f"Request to join existing block {target_block.block_code}",
    )
    return create_integration(create_payload, current_user, db)


@router.get("/blocks/{block_id}/integrations", response_model=IntegrationListResponse)
def integrations_for_block(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    block = _get_block(db, block_id)
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        is_participant = db.query(BlockIntegrationRequest).filter(
            ((BlockIntegrationRequest.source_block_id == block_id) | (BlockIntegrationRequest.target_block_id == block_id))
            & ((BlockIntegrationRequest.requesting_department_id == current_user.department_id) | (BlockIntegrationRequest.target_department_id == current_user.department_id))
        ).first()
        if not is_participant and current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    query = db.query(BlockIntegrationRequest).filter(
        (BlockIntegrationRequest.source_block_id == block_id) | (BlockIntegrationRequest.target_block_id == block_id)
    )
    total = query.count()
    items = query.order_by(BlockIntegrationRequest.id.desc()).all()
    return IntegrationListResponse(total=total, items=[_to_out(i, db) for i in items], skip=0, limit=100)
