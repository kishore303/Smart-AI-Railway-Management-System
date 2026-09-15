from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.block import BlockRequest, BlockIntegrationRequest
from app.models.maintenance import MaintenanceRequest
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.schemas.integration import IntegrationCreate, IntegrationOut, IntegrationListResponse, IntegrationRespond

router = APIRouter(prefix="/api/integration", tags=["integration"])

# Roles allowed to create/respond
INTEGRATION_CREATE_ROLES = {"MAINTENANCE_STAFF", "ENGINEER_REVIEWER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}
INTEGRATION_RESPOND_ROLES = {"ENGINEER_REVIEWER", "CONTROLLER", "AUTHORIZED_OFFICIAL", "MAINTENANCE_STAFF"}


def _audit(db: Session, user_id, action, entity_id=None, old=None, new=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="block_integration_request", entity_id=entity_id, old_status=old, new_status=new, description=desc)
    db.add(log)
    db.commit()


def _notify(db: Session, recipient_dept_id: int, type_: str, title: str, message: str, integration_id: int = None):
    n = Notification(
        recipient_department_id=recipient_dept_id,
        type=type_,
        title=title,
        message=message,
        priority="NORMAL",
        integration_request_id=integration_id,
    )
    db.add(n)
    db.commit()


def _get_block_dept(db: Session, block_id: int) -> int:
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Block {block_id} not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance for block not found")
    return mreq.department_id


def _get_block(db: Session, block_id: int) -> BlockRequest:
    b = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Block {block_id} not found")
    return b


def _compute_overlap(a_start, a_end, b_start, b_end) -> int:
    latest_start = max(a_start, b_start)
    earliest_end = min(a_end, b_end)
    if latest_start >= earliest_end:
        return 0
    return int((earliest_end - latest_start).total_seconds() // 60)


def _to_out(req: BlockIntegrationRequest, db: Session) -> IntegrationOut:
    req_dept = db.query(Department).filter(Department.id == req.requesting_department_id).first()
    tgt_dept = db.query(Department).filter(Department.id == req.target_department_id).first()
    return IntegrationOut(
        id=req.id,
        source_block_id=req.source_block_id,
        target_block_id=req.target_block_id,
        requesting_department_id=req.requesting_department_id,
        requesting_department_code=req_dept.code if req_dept else "UNKNOWN",
        target_department_id=req.target_department_id,
        target_department_code=tgt_dept.code if tgt_dept else "UNKNOWN",
        overlap_duration_mins=req.overlap_duration_mins,
        compatibility_status=req.compatibility_status,
        requested_by=req.requested_by,
        response_by=req.response_by,
        response=req.response,
        reason=req.reason,
        final_status=req.final_status,
        created_at=req.created_at,
    )


@router.post("/requests", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(payload: IntegrationCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in INTEGRATION_CREATE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot create integration")
    if payload.source_block_id == payload.target_block_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Source and target must differ")

    src = _get_block(db, payload.source_block_id)
    tgt = _get_block(db, payload.target_block_id)

    src_dept = _get_block_dept(db, payload.source_block_id)
    tgt_dept = _get_block_dept(db, payload.target_block_id)

    if src_dept == tgt_dept:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cross-department integration requires different departments")

    # Requester must belong to requesting department
    if current_user.department_id != src_dept and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester must belong to source block's department")

    # Validate target department exists (derived)
    # Check duplicate active
    existing = db.query(BlockIntegrationRequest).filter(
        BlockIntegrationRequest.source_block_id == payload.source_block_id,
        BlockIntegrationRequest.target_block_id == payload.target_block_id,
        BlockIntegrationRequest.final_status == "PENDING",
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active integration request already exists for this pair")

    # Also check reverse pair duplicate? Consider same pair reverse as duplicate
    existing_rev = db.query(BlockIntegrationRequest).filter(
        BlockIntegrationRequest.source_block_id == payload.target_block_id,
        BlockIntegrationRequest.target_block_id == payload.source_block_id,
        BlockIntegrationRequest.final_status == "PENDING",
    ).first()
    if existing_rev:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reverse active integration already exists")

    # Planning-level compatibility: same section, overlapping time
    # Use block's section/track
    overlap = _compute_overlap(src.requested_start, src.requested_end, tgt.requested_start, tgt.requested_end)
    same_section = src.section_id == tgt.section_id
    same_track = src.track_id == tgt.track_id

    if same_section and overlap > 0:
        # Overlapping same section => compatible at planning level, but still requires safety
        compat = "COMPATIBLE"
    elif same_section and overlap == 0:
        compat = "POTENTIALLY_COMPATIBLE"
    else:
        compat = "REQUIRES_SAFETY_VALIDATION"
        # Still allow creation, but mark as requires safety

    # Do NOT claim safe — use COMPATIBLE terminology, not SAFE
    req = BlockIntegrationRequest(
        source_block_id=payload.source_block_id,
        target_block_id=payload.target_block_id,
        requesting_department_id=src_dept,
        target_department_id=tgt_dept,
        overlap_duration_mins=overlap if overlap > 0 else None,
        compatibility_status=compat,
        requested_by=current_user.id,
        final_status="PENDING",
        reason=payload.reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    _audit(db, current_user.id, "REQUEST_INTEGRATION", entity_id=req.id, old=None, new="PENDING", desc=f"{src_dept}->{tgt_dept} blocks {payload.source_block_id}->{payload.target_block_id} compat={compat}")
    # Targeted notification to target department
    _notify(db, tgt_dept, "BLOCK_INTEGRATION_OPPORTUNITY", f"Integration request from {src_dept} to {tgt_dept}", f"Block {src.block_code} proposes integration with {tgt.block_code}. Compat: {compat}", integration_id=req.id)
    return _to_out(req, db)


@router.get("/requests", response_model=IntegrationListResponse)
def list_integrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER")
    query = db.query(BlockIntegrationRequest)
    if not is_privileged:
        # Dept-scoped: as requester or target
        query = query.filter(
            (BlockIntegrationRequest.requesting_department_id == current_user.department_id)
            | (BlockIntegrationRequest.target_department_id == current_user.department_id)
        )
    if status:
        query = query.filter(BlockIntegrationRequest.final_status == status)
    total = query.count()
    items = query.order_by(BlockIntegrationRequest.id.desc()).offset(skip).limit(limit).all()
    return IntegrationListResponse(total=total, items=[_to_out(i, db) for i in items], skip=skip, limit=limit)


@router.get("/requests/{integration_id}", response_model=IntegrationOut)
def get_integration(integration_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER")
    if not is_privileged and current_user.department_id not in (req.requesting_department_id, req.target_department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return _to_out(req, db)


@router.post("/requests/{integration_id}/respond", response_model=IntegrationOut)
def respond_integration(integration_id: int, payload: IntegrationRespond, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in INTEGRATION_RESPOND_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot respond")
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if req.final_status != "PENDING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot respond to {req.final_status} request")
    # Only target department can respond
    if current_user.department_id != req.target_department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only target department can respond")
    # Self-approval: requester cannot approve own
    if current_user.id == req.requested_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester cannot respond to own integration")

    resp = payload.response.strip().upper()
    if resp not in ("ACCEPT", "REJECT", "MODIFY"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Response must be ACCEPT, REJECT, or MODIFY")

    mapping = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "MODIFY": "MODIFIED"}
    old = req.final_status
    req.response = resp
    req.response_by = current_user.id
    req.reason = payload.reason if payload.reason else req.reason
    req.final_status = mapping[resp]
    db.commit()
    db.refresh(req)
    audit_action = {"ACCEPT": "ACCEPT_INTEGRATION", "REJECT": "REJECT_INTEGRATION", "MODIFY": "MODIFY_INTEGRATION"}[resp]
    _audit(db, current_user.id, audit_action, entity_id=req.id, old=old, new=req.final_status, desc=payload.reason)
    # Notify requester
    ntype = {"ACCEPT": "INTEGRATION_ACCEPTED", "REJECT": "INTEGRATION_REJECTED", "MODIFY": "BLOCK_INTEGRATION_OPPORTUNITY"}[resp]
    _notify(db, req.requesting_department_id, ntype, f"Integration {resp} by target", f"Request {req.id} {resp}: {payload.reason or ''}", integration_id=req.id)
    # Also ensure no auto-merge: we do NOT create optimized_blocks here
    return _to_out(req, db)


@router.post("/requests/{integration_id}/cancel", response_model=IntegrationOut)
def cancel_integration(integration_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(BlockIntegrationRequest).filter(BlockIntegrationRequest.id == integration_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if req.final_status != "PENDING":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only PENDING can be cancelled")
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


@router.get("/blocks/{block_id}/integrations", response_model=IntegrationListResponse)
def integrations_for_block(block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Check access to block
    block = db.query(BlockRequest).filter(BlockRequest.id == block_id).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq or not can_access_department_resource(current_user, mreq.department_id, db):
        # Allow if user is part of any integration for this block
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
