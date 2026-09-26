from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user, require_roles, can_access_department_resource, check_self_approval
from app.models.user import User
from app.models.department import Department
from app.models.maintenance import MaintenanceRequest, MaintenanceArea
from app.models.asset import Asset
from app.models.railway import RailwaySection, Track
from app.models.resource import Resource
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceUpdate,
    MaintenanceOut,
    MaintenanceListResponse,
    StatusTransition,
    ReviewAction,
    ReasonPayload,
    SubmitPayload,
    ReviewHistoryItem,
    ReviewQueueResponse,
    MaintenanceAreaCreate,
    MaintenanceAreaUpdate,
    MaintenanceAreaOut,
)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

# Valid priorities
VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

# Status transition map — ensures no stage skip
# Includes full lifecycle to BLOCK_PLANNING etc., but Module 4 primarily uses up to VERIFIED/REJECTED
ALLOWED_TRANSITIONS = {
    "DRAFT": {"SUBMITTED"},
    "SUBMITTED": {"UNDER_REVIEW", "REVISION_REQUIRED", "REJECTED"},
    "UNDER_REVIEW": {"VERIFIED", "REJECTED", "REVISION_REQUIRED"},
    "REVISION_REQUIRED": {"SUBMITTED", "DRAFT"},
    "VERIFIED": {"BLOCK_PLANNING"},
    "BLOCK_PLANNING": {"AI_RECOMMENDATION"},
    "AI_RECOMMENDATION": {"OFFICIAL_REVIEW"},
    "OFFICIAL_REVIEW": {"APPROVED", "MODIFIED", "REJECTED"},
    "PENDING": {"UNDER_REVIEW", "REJECTED"},  # legacy support
    # Terminal states have no outgoing (except REVISION can cycle)
}

# Role required for each target status
STATUS_ROLE_MAP = {
    "SUBMITTED": {"MAINTENANCE_STAFF", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "UNDER_REVIEW": {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "VERIFIED": {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "REJECTED": {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "AUTHORIZED_OFFICIAL"},
    "REVISION_REQUIRED": {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"},
    "BLOCK_PLANNING": {"SENIOR_SECTION_ENGINEER", "AUTHORIZED_OFFICIAL"},
    "APPROVED": {"AUTHORIZED_OFFICIAL"},
    "MODIFIED": {"AUTHORIZED_OFFICIAL"},
}


def _audit(db: Session, user_id, action, entity_id=None, old=None, new=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="maintenance_request", entity_id=entity_id, old_status=old, new_status=new, description=desc)
    db.add(log)
    db.commit()


def _notify(
    db: Session,
    type_: str,
    title: str,
    message: Optional[str] = None,
    recipient_user_id: Optional[int] = None,
    recipient_dept_id: Optional[int] = None,
    section_id: Optional[int] = None,
    track_id: Optional[int] = None,
    priority: str = "NORMAL",
):
    try:
        notif = Notification(
            recipient_user_id=recipient_user_id,
            recipient_department_id=recipient_dept_id,
            type=type_,
            title=title,
            message=message,
            section_id=section_id,
            track_id=track_id,
            priority=priority,
        )
        db.add(notif)
        db.commit()
    except Exception:
        db.rollback()


def _gen_code(db: Session):
    # Simple: REQ-YYYYMMDD-XXXX (count+1)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    cnt = db.query(MaintenanceRequest).count() + 1
    return f"REQ-{today}-{cnt:04d}"


def _to_out(req: MaintenanceRequest, db: Session) -> MaintenanceOut:
    dept = db.query(Department).filter(Department.id == req.department_id).first()
    code = dept.code if dept else "UNKNOWN"
    return MaintenanceOut(
        id=req.id,
        request_code=req.request_code,
        asset_id=req.asset_id,
        department_id=req.department_id,
        department_code=code,
        requested_by=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        maintenance_type=req.maintenance_type,
        description=req.description,
        priority=req.priority,
        requested_start=req.requested_start,
        requested_end=req.requested_end,
        requested_duration_mins=req.requested_duration_mins,
        status=req.status,
        reviewed_by=req.reviewed_by,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
        revision_notes=req.revision_notes,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def _validate_time(start: datetime, end: datetime):
    if end <= start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="requested_end must be after requested_start")
    # Optional: must be future? Allow near-future synthetic tests, but reject past far?
    # Not enforcing strict future for test flexibility


def _validate_relationships(db: Session, asset_id, section_id, track_id, priority):
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid priority {priority}")
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    section = db.query(RailwaySection).filter(RailwaySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    # Asset must belong to section or at least asset.section_id matches if asset has section
    if asset.section_id and asset.section_id != section_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Asset does not belong to section")
    if track_id:
        track = db.query(Track).filter(Track.id == track_id).first()
        if not track:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        if track.section_id != section_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Track does not belong to section")
        if asset.track_id and asset.track_id != track_id:
            # Allow if asset has no track or same track; otherwise warn but not hard fail? We enforce strict
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Asset track mismatch")


def _validate_resources(db: Session, resource_ids):
    if not resource_ids:
        return
    for rid in resource_ids:
        r = db.query(Resource).filter(Resource.id == rid).first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resource {rid} not found")
        if not r.is_available:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Resource {r.resource_code} not available")


@router.post("/requests", response_model=MaintenanceOut, status_code=status.HTTP_201_CREATED)
def create_request(payload: MaintenanceCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # RBAC: maintenance staff and departmental engineers can create requests
    if current_user.role not in ("MAINTENANCE_STAFF", "ENGINEER_REVIEWER", "JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only MAINTENANCE_STAFF or departmental engineers can create requests")
    # Dept check: request dept is current_user dept (or asset dept? We use current_user dept)
    _validate_time(payload.requested_start, payload.requested_end)

    _validate_relationships(db, payload.asset_id, payload.section_id, payload.track_id, payload.priority)
    _validate_resources(db, payload.resource_ids)

    # Asset must be accessible: staff can only create for own dept assets? Enforce asset.department_id == current_user.department_id unless official?
    asset = db.query(Asset).filter(Asset.id == payload.asset_id).first()
    if asset.department_id != current_user.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Asset department mismatch")

    duration = int((payload.requested_end - payload.requested_start).total_seconds() // 60)
    code = _gen_code(db)
    req = MaintenanceRequest(
        request_code=code,
        asset_id=payload.asset_id,
        department_id=current_user.department_id,
        requested_by=current_user.id,
        section_id=payload.section_id,
        track_id=payload.track_id,
        maintenance_type=payload.maintenance_type,
        description=payload.description,
        priority=payload.priority,
        requested_start=payload.requested_start,
        requested_end=payload.requested_end,
        requested_duration_mins=duration,
        status="DRAFT",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    _audit(db, current_user.id, "CREATE_MAINTENANCE_REQUEST", entity_id=req.id, old=None, new="DRAFT", desc=f"Created {code}")
    return _to_out(req, db)


@router.get("/requests", response_model=MaintenanceListResponse)
def list_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    department_code: Optional[str] = Query(None),
    section_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(MaintenanceRequest)
    # Dept-scoped: non-privileged see only own dept
    is_privileged = current_user.role in ("AUTHORIZED_OFFICIAL", "CONTROLLER", "EMERGENCY_OPERATOR")
    if not is_privileged:
        query = query.filter(MaintenanceRequest.department_id == current_user.department_id)
        if department_code:
            own = db.query(Department).filter(Department.id == current_user.department_id).first()
            if department_code != own.code:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department filter denied")
    else:
        if department_code:
            dept = db.query(Department).filter(Department.code == department_code).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
            query = query.filter(MaintenanceRequest.department_id == dept.id)
    if status_filter:
        query = query.filter(MaintenanceRequest.status == status_filter)
    if section_id:
        query = query.filter(MaintenanceRequest.section_id == section_id)
    if priority:
        query = query.filter(MaintenanceRequest.priority == priority)
    total = query.count()
    items = query.order_by(MaintenanceRequest.id.desc()).offset(skip).limit(limit).all()
    out = [_to_out(i, db) for i in items]
    return MaintenanceListResponse(total=total, items=out, skip=skip, limit=limit)


@router.get("/requests/{request_id}", response_model=MaintenanceOut)
def get_request(request_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if not can_access_department_resource(current_user, req.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return _to_out(req, db)


@router.patch("/requests/{request_id}", response_model=MaintenanceOut)
def update_request(request_id: int, payload: MaintenanceUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    # Only owner can update, and only in DRAFT or REVISION_REQUIRED
    if req.requested_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requester can update")
    if req.status not in ("DRAFT", "REVISION_REQUIRED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot update in status {req.status}")

    # Apply updates with validation
    if payload.priority and payload.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid priority")
    new_start = payload.requested_start if payload.requested_start else req.requested_start
    new_end = payload.requested_end if payload.requested_end else req.requested_end
    if payload.requested_start or payload.requested_end:
        _validate_time(new_start, new_end)
    # Relationships if changed
    new_asset = payload.asset_id if hasattr(payload, "asset_id") and payload.asset_id else req.asset_id  # not in update schema, ignore
    # For simplicity, only track_id/priority validated
    if payload.track_id is not None or payload.priority:
        # reuse current asset/section for validation
        _validate_relationships(db, req.asset_id, req.section_id, payload.track_id if payload.track_id is not None else req.track_id, payload.priority if payload.priority else req.priority)

    if payload.maintenance_type is not None:
        req.maintenance_type = payload.maintenance_type
    if payload.description is not None:
        req.description = payload.description
    if payload.priority is not None:
        req.priority = payload.priority
    if payload.requested_start is not None:
        req.requested_start = payload.requested_start
    if payload.requested_end is not None:
        req.requested_end = payload.requested_end
        req.requested_duration_mins = int((req.requested_end - req.requested_start).total_seconds() // 60)
    if payload.track_id is not None:
        req.track_id = payload.track_id
    if payload.resource_ids is not None:
        _validate_resources(db, payload.resource_ids)

    db.commit()
    db.refresh(req)
    _audit(db, current_user.id, "UPDATE_MAINTENANCE_REQUEST", entity_id=req.id, old=req.status, new=req.status, desc="Updated fields")
    return _to_out(req, db)


@router.post("/requests/{request_id}/transition", response_model=MaintenanceOut)
def transition_request(request_id: int, payload: StatusTransition, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    new_status = payload.new_status
    old_status = req.status

    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot transition {old_status} -> {new_status}")

    # Role checks per target
    required_roles = STATUS_ROLE_MAP.get(new_status)
    if required_roles and current_user.role not in required_roles:
        # Special: SUBMITTED can be done by requester (MAINTENANCE_STAFF) — already checked, but also need owner check
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role {current_user.role} cannot transition to {new_status}")

    # Owner vs reviewer checks
    if new_status == "SUBMITTED":
        if req.requested_by != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requester can submit")
    if new_status in ("UNDER_REVIEW", "VERIFIED", "REJECTED", "REVISION_REQUIRED"):
        if req.requested_by == current_user.id:
            check_self_approval(current_user.id, req.requested_by)
        # UNDER_REVIEW etc. should be same dept reviewer
        if req.department_id != current_user.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer department mismatch")
        if old_status == "SUBMITTED" and new_status == "UNDER_REVIEW":
            pass  # ok
        if new_status in ("VERIFIED", "REJECTED", "REVISION_REQUIRED") and old_status != "UNDER_REVIEW":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review actions require UNDER_REVIEW")

    # Apply
    req.status = new_status
    if new_status in ("VERIFIED", "REJECTED", "REVISION_REQUIRED"):
        req.reviewed_by = current_user.id
        req.reviewed_at = datetime.now(timezone.utc)
        if new_status == "REJECTED":
            req.rejection_reason = payload.reason
        if new_status == "REVISION_REQUIRED":
            req.revision_notes = payload.reason

    db.commit()
    db.refresh(req)
    _audit(db, current_user.id, f"TRANSITION_{new_status}", entity_id=req.id, old=old_status, new=new_status, desc=payload.reason)
    _audit(db, current_user.id, "UPDATE_MAINTENANCE_REQUEST_STATUS", entity_id=req.id, old=old_status, new=new_status, desc=payload.reason)

    # Notifications
    if new_status == "SUBMITTED":
        _notify(db, "NEW_MAINTENANCE_REQUEST", f"New Maintenance Request {req.request_code}", message=f"Maintenance request {req.request_code} has been submitted for technical review.", recipient_dept_id=req.department_id, section_id=req.section_id, track_id=req.track_id)
    elif new_status == "VERIFIED":
        _notify(db, "REQUEST_VERIFICATION", f"Request {req.request_code} Verified", message=f"Maintenance request {req.request_code} has been verified.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id)
    elif new_status == "REVISION_REQUIRED":
        _notify(db, "REVISION_REQUIRED", f"Revision Required: {req.request_code}", message=payload.reason or "Please revise maintenance request details.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id, priority="HIGH")
    elif new_status == "REJECTED":
        _notify(db, "BLOCK_REJECTED", f"Request Rejected: {req.request_code}", message=payload.reason or "Maintenance request was rejected.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id, priority="HIGH")

    return _to_out(req, db)


# ==================== Dedicated Workflow Endpoints ====================

@router.post("/requests/{request_id}/submit", response_model=MaintenanceOut)
def submit_request(request_id: int, payload: Optional[SubmitPayload] = None, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.requested_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only request creator can submit request")
    if req.status not in ("DRAFT", "REVISION_REQUIRED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot submit request in status {req.status}")

    old = req.status
    req.status = "SUBMITTED"
    db.commit()
    db.refresh(req)

    notes = payload.notes if payload else None
    _audit(db, current_user.id, "REQUEST_SUBMITTED", entity_id=req.id, old=old, new="SUBMITTED", desc=notes or "Submitted for JE review")
    _audit(db, current_user.id, "TRANSITION_SUBMITTED", entity_id=req.id, old=old, new="SUBMITTED", desc=notes or "Submitted for JE review")
    _notify(
        db,
        "NEW_MAINTENANCE_REQUEST",
        f"New Maintenance Request {req.request_code}",
        message=f"Request {req.request_code} submitted for technical review ({req.maintenance_type}).",
        recipient_dept_id=req.department_id,
        section_id=req.section_id,
        track_id=req.track_id,
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/je/verify", response_model=MaintenanceOut)
def je_verify(request_id: int, payload: Optional[ReasonPayload] = None, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("JUNIOR_ENGINEER", "ENGINEER_REVIEWER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Junior Engineers can perform JE verification")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="JE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    if req.status not in ("SUBMITTED", "UNDER_REVIEW"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot perform JE verification on request in status {req.status}")

    old = req.status
    req.status = "UNDER_REVIEW"  # JE verified, forwarded to SSE review
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)

    comment = payload.reason if payload else "JE Technical Verification completed"
    _audit(db, current_user.id, "JE_VERIFIED", entity_id=req.id, old=old, new="UNDER_REVIEW", desc=comment)
    _audit(db, current_user.id, "TRANSITION_UNDER_REVIEW", entity_id=req.id, old=old, new="UNDER_REVIEW", desc=comment)
    _notify(
        db,
        "REQUEST_VERIFICATION",
        f"JE Verified — Awaiting SSE Review: {req.request_code}",
        message=f"Request {req.request_code} verified by JE {current_user.name}. Forwarded to SSE for verification.",
        recipient_dept_id=req.department_id,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="HIGH",
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/je/revision", response_model=MaintenanceOut)
def je_revision(request_id: int, payload: ReasonPayload, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("JUNIOR_ENGINEER", "ENGINEER_REVIEWER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Junior Engineers can request JE revision")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="JE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    if req.status not in ("SUBMITTED", "UNDER_REVIEW"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot request revision on request in status {req.status}")

    old = req.status
    req.status = "REVISION_REQUIRED"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.revision_notes = payload.reason
    db.commit()
    db.refresh(req)

    _audit(db, current_user.id, "JE_REVISION_REQUESTED", entity_id=req.id, old=old, new="REVISION_REQUIRED", desc=payload.reason)
    _audit(db, current_user.id, "REVISION_REQUIRED", entity_id=req.id, old=old, new="REVISION_REQUIRED", desc=payload.reason)
    _notify(
        db,
        "REVISION_REQUIRED",
        f"JE Revision Required: {req.request_code}",
        message=payload.reason,
        recipient_user_id=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="HIGH",
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/je/reject", response_model=MaintenanceOut)
def je_reject(request_id: int, payload: ReasonPayload, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("JUNIOR_ENGINEER", "ENGINEER_REVIEWER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Junior Engineers can reject requests")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="JE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    if req.status not in ("SUBMITTED", "UNDER_REVIEW"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot reject request in status {req.status}")

    old = req.status
    req.status = "REJECTED"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_reason = payload.reason
    db.commit()
    db.refresh(req)

    _audit(db, current_user.id, "JE_REJECTED", entity_id=req.id, old=old, new="REJECTED", desc=payload.reason)
    _audit(db, current_user.id, "REJECT_MAINTENANCE_REQUEST", entity_id=req.id, old=old, new="REJECTED", desc=payload.reason)
    _notify(
        db,
        "BLOCK_REJECTED",
        f"Request Rejected by JE: {req.request_code}",
        message=payload.reason,
        recipient_user_id=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="HIGH",
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/sse/verify", response_model=MaintenanceOut)
def sse_verify(request_id: int, payload: Optional[ReasonPayload] = None, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("SENIOR_SECTION_ENGINEER", "AUTHORIZED_OFFICIAL"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Senior Section Engineers can perform SSE verification")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    # SSE requires prior JE review (status must be UNDER_REVIEW or have reviewer recorded)
    if req.status == "SUBMITTED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SSE verification requires prior JE technical review (request is still SUBMITTED)")
    if req.status != "UNDER_REVIEW":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot perform SSE verification on request in status {req.status}")

    old = req.status
    req.status = "VERIFIED"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)

    comment = payload.reason if payload else "SSE Senior Verification completed — Ready for Planning"
    _audit(db, current_user.id, "SSE_VERIFIED", entity_id=req.id, old=old, new="VERIFIED", desc=comment)
    _audit(db, current_user.id, "VERIFY_MAINTENANCE_REQUEST", entity_id=req.id, old=old, new="VERIFIED", desc=comment)
    _audit(db, current_user.id, "TRANSITION_VERIFIED", entity_id=req.id, old=old, new="VERIFIED", desc=comment)
    _notify(
        db,
        "REQUEST_VERIFICATION",
        f"Maintenance Request Verified: {req.request_code}",
        message=f"Request {req.request_code} has been verified by SSE {current_user.name} and is ready for planning.",
        recipient_user_id=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="NORMAL",
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/sse/revision", response_model=MaintenanceOut)
def sse_revision(request_id: int, payload: ReasonPayload, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("SENIOR_SECTION_ENGINEER", "AUTHORIZED_OFFICIAL"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Senior Section Engineers can request SSE revision")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    if req.status not in ("SUBMITTED", "UNDER_REVIEW"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot request revision on request in status {req.status}")

    old = req.status
    req.status = "REVISION_REQUIRED"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.revision_notes = payload.reason
    db.commit()
    db.refresh(req)

    _audit(db, current_user.id, "SSE_REVISION_REQUESTED", entity_id=req.id, old=old, new="REVISION_REQUIRED", desc=payload.reason)
    _audit(db, current_user.id, "REVISION_REQUIRED", entity_id=req.id, old=old, new="REVISION_REQUIRED", desc=payload.reason)
    _notify(
        db,
        "REVISION_REQUIRED",
        f"SSE Revision Required: {req.request_code}",
        message=payload.reason,
        recipient_user_id=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="HIGH",
    )
    return _to_out(req, db)


@router.post("/requests/{request_id}/sse/reject", response_model=MaintenanceOut)
def sse_reject(request_id: int, payload: ReasonPayload, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("SENIOR_SECTION_ENGINEER", "AUTHORIZED_OFFICIAL"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Senior Section Engineers can reject requests")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSE department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    if req.status not in ("SUBMITTED", "UNDER_REVIEW"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot reject request in status {req.status}")

    old = req.status
    req.status = "REJECTED"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_reason = payload.reason
    db.commit()
    db.refresh(req)

    _audit(db, current_user.id, "SSE_REJECTED", entity_id=req.id, old=old, new="REJECTED", desc=payload.reason)
    _audit(db, current_user.id, "REJECT_MAINTENANCE_REQUEST", entity_id=req.id, old=old, new="REJECTED", desc=payload.reason)
    _notify(
        db,
        "BLOCK_REJECTED",
        f"Request Rejected by SSE: {req.request_code}",
        message=payload.reason,
        recipient_user_id=req.requested_by,
        section_id=req.section_id,
        track_id=req.track_id,
        priority="HIGH",
    )
    return _to_out(req, db)


# ==================== Module 5 — Review & Verification ====================

REVIEW_ACTION_MAP = {
    "VERIFY": "VERIFIED",
    "VERIFIED": "VERIFIED",
    "APPROVE": "VERIFIED",
    "REJECT": "REJECTED",
    "REJECTED": "REJECTED",
    "REVISION_REQUIRED": "REVISION_REQUIRED",
    "REVISION": "REVISION_REQUIRED",
    "NEEDS_REVISION": "REVISION_REQUIRED",
}

AUDIT_ACTION_MAP = {
    "VERIFIED": "VERIFY_MAINTENANCE_REQUEST",
    "REJECTED": "REJECT_MAINTENANCE_REQUEST",
    "REVISION_REQUIRED": "REVISION_REQUIRED",
}


@router.get("/review/queue", response_model=ReviewQueueResponse)
def review_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "ENGINEER_REVIEWER", "AUTHORIZED_OFFICIAL"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Technical Reviewers (JE / SSE) can access review queue")
    base = db.query(MaintenanceRequest)
    if current_user.role != "AUTHORIZED_OFFICIAL":
        base = base.filter(MaintenanceRequest.department_id == current_user.department_id)
    if status_filter:
        base = base.filter(MaintenanceRequest.status == status_filter)
    else:
        base = base.filter(MaintenanceRequest.status.in_(["SUBMITTED", "UNDER_REVIEW"]))
    total = base.count()
    items = base.order_by(MaintenanceRequest.id.desc()).offset(skip).limit(limit).all()
    out = [_to_out(i, db) for i in items]
    return ReviewQueueResponse(total=total, items=out, skip=skip, limit=limit)


@router.post("/requests/{request_id}/review", response_model=MaintenanceOut)
def review_request(request_id: int, payload: ReviewAction, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role not in ("JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "ENGINEER_REVIEWER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Technical Reviewers (JE / SSE) can review")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.department_id != current_user.department_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer department mismatch")
    check_self_approval(current_user.id, req.requested_by)

    raw = payload.action.strip().upper()
    target_status = REVIEW_ACTION_MAP.get(raw)
    if not target_status:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid review action {payload.action}")
    if target_status not in ALLOWED_TRANSITIONS.get(req.status, set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot review {req.status} -> {target_status}")
    if target_status in ("VERIFIED", "REJECTED", "REVISION_REQUIRED") and req.status != "UNDER_REVIEW":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Review action {target_status} requires UNDER_REVIEW")

    reason = payload.reason or payload.rejection_reason or payload.revision_notes
    old = req.status
    req.status = target_status
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)
    if target_status == "REJECTED":
        req.rejection_reason = reason
    elif target_status == "REVISION_REQUIRED":
        req.revision_notes = reason

    db.commit()
    db.refresh(req)
    audit_action = AUDIT_ACTION_MAP.get(target_status, f"REVIEW_{target_status}")
    _audit(db, current_user.id, audit_action, entity_id=req.id, old=old, new=target_status, desc=reason)
    _audit(db, current_user.id, "UPDATE_MAINTENANCE_REQUEST_STATUS", entity_id=req.id, old=old, new=target_status, desc=reason)

    if target_status == "VERIFIED":
        _notify(db, "REQUEST_VERIFICATION", f"Request {req.request_code} Verified", message=f"Maintenance request {req.request_code} has been verified.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id)
    elif target_status == "REVISION_REQUIRED":
        _notify(db, "REVISION_REQUIRED", f"Revision Required: {req.request_code}", message=reason or "Please revise maintenance request details.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id, priority="HIGH")
    elif target_status == "REJECTED":
        _notify(db, "BLOCK_REJECTED", f"Request Rejected: {req.request_code}", message=reason or "Maintenance request was rejected.", recipient_user_id=req.requested_by, section_id=req.section_id, track_id=req.track_id, priority="HIGH")

    return _to_out(req, db)


@router.get("/requests/{request_id}/history", response_model=list[ReviewHistoryItem])
def review_history(request_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if not can_access_department_resource(current_user, req.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    logs = db.query(AuditLog).filter(AuditLog.entity_type == "maintenance_request", AuditLog.entity_id == request_id).order_by(AuditLog.created_at.asc()).all()
    result = []
    for log in logs:
        uname = None
        urole = None
        if log.user_id:
            u = db.query(User).filter(User.id == log.user_id).first()
            if u:
                uname = u.name
                urole = u.role
        result.append(ReviewHistoryItem(id=log.id, action=log.action, user_id=log.user_id, user_name=uname, user_role=urole, old_status=log.old_status, new_status=log.new_status, description=log.description, created_at=log.created_at))
    return result


# ==================== Maintenance Area Endpoints ====================

from app.schemas.maintenance import MaintenanceAreaCreate, MaintenanceAreaUpdate, MaintenanceAreaOut


def _validate_km_range(start_km: float, end_km: float):
    if start_km <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Start KM must be positive")
    if end_km <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be positive")
    if end_km <= start_km:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be greater than Start KM")


def _validate_track_section(db: Session, track_id: int, section_id: int):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    if track.section_id != section_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Track does not belong to the selected section")


@router.get("/requests/{request_id}/maintenance-area", response_model=MaintenanceAreaOut)
def get_maintenance_area(request_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
    if not can_access_department_resource(current_user, req.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    area = db.query(MaintenanceArea).filter(MaintenanceArea.maintenance_request_id == request_id).first()
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance area not defined for this request")

    defined_by_user = db.query(User).filter(User.id == area.defined_by).first()
    return MaintenanceAreaOut(
        id=area.id,
        maintenance_request_id=area.maintenance_request_id,
        section_id=area.section_id,
        track_id=area.track_id,
        start_km=float(area.start_km),
        end_km=float(area.end_km),
        length_km=float(area.length_km),
        defined_by=area.defined_by,
        defined_by_name=defined_by_user.name if defined_by_user else None,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )


@router.post("/requests/{request_id}/maintenance-area", response_model=MaintenanceAreaOut, status_code=status.HTTP_201_CREATED)
def create_maintenance_area(
    request_id: int,
    payload: MaintenanceAreaCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")

    # Only SSE can create maintenance areas
    if current_user.role != "SENIOR_SECTION_ENGINEER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SSE can define maintenance areas")

    # Check department access
    if current_user.department_id != req.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSE can only define areas for their own department")

    # Validate KM range
    if payload.start_km <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Start KM must be positive")
    if payload.end_km <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be positive")
    if payload.end_km <= payload.start_km:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be greater than Start KM")

    # Validate track belongs to section
    track = db.query(Track).filter(Track.id == payload.track_id).first()
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    if track.section_id != payload.section_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Track does not belong to the selected section")

    # Check if area already exists
    existing = db.query(MaintenanceArea).filter(MaintenanceArea.maintenance_request_id == request_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maintenance area already defined for this request")

    length_km = payload.end_km - payload.start_km

    area = MaintenanceArea(
        maintenance_request_id=request_id,
        section_id=payload.section_id,
        track_id=payload.track_id,
        start_km=payload.start_km,
        end_km=payload.end_km,
        length_km=payload.end_km - payload.start_km,
        defined_by=current_user.id,
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    _audit(db, current_user.id, "CREATE_MAINTENANCE_AREA", entity_id=area.id, old=None, new=area.length_km, desc=f"Defined area {area.start_km}-{area.end_km} km for request {request_id}")

    defined_by_user = db.query(User).filter(User.id == area.defined_by).first()
    return MaintenanceAreaOut(
        id=area.id,
        maintenance_request_id=area.maintenance_request_id,
        section_id=area.section_id,
        track_id=area.track_id,
        start_km=float(area.start_km),
        end_km=float(area.end_km),
        length_km=float(area.length_km),
        defined_by=area.defined_by,
        defined_by_name=defined_by_user.name if defined_by_user else None,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )


@router.put("/requests/{request_id}/maintenance-area", response_model=MaintenanceAreaOut)
def update_maintenance_area(
    request_id: int,
    payload: MaintenanceAreaUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    area = db.query(MaintenanceArea).filter(MaintenanceArea.maintenance_request_id == request_id).first()
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance area not defined for this request")

    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")

    # Only SSE can update maintenance areas
    if current_user.role != "SENIOR_SECTION_ENGINEER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SSE can update maintenance areas")

    # Check department access
    if current_user.department_id != req.department_id and current_user.role != "AUTHORIZED_OFFICIAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSE can only update areas for their own department")

    # Validate updates
    if payload.start_km is not None:
        if payload.start_km <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Start KM must be positive")
        if area.end_km <= payload.start_km:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be greater than Start KM")
        area.start_km = payload.start_km

    if payload.end_km is not None:
        if payload.end_km <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be positive")
        if payload.end_km <= area.start_km:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End KM must be greater than Start KM")
        area.end_km = payload.end_km

    area.length_km = area.end_km - area.start_km
    db.commit()
    db.refresh(area)

    _audit(db, current_user.id, "UPDATE_MAINTENANCE_AREA", entity_id=area.id, old=None, new=area.length_km, desc=f"Updated area to {area.start_km}-{area.end_km} km for request {request_id}")

    defined_by_user = db.query(User).filter(User.id == area.defined_by).first()
    return MaintenanceAreaOut(
        id=area.id,
        maintenance_request_id=area.maintenance_request_id,
        section_id=area.section_id,
        track_id=area.track_id,
        start_km=float(area.start_km),
        end_km=float(area.end_km),
        length_km=float(area.length_km),
        defined_by=area.defined_by,
        defined_by_name=defined_by_user.name if defined_by_user else None,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )

