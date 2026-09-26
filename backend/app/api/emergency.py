from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.core.rbac import get_current_active_user
from app.models.user import User
from app.models.incident import Incident, EmergencyResponse
from app.models.block import BlockRequest, BlockCandidate, OptimizedBlock
from app.services.emergency_service import EmergencyService
from app.optimizer.engine import build_candidate_comparison_matrix

router = APIRouter(prefix="/api/emergency", tags=["emergency"])

ALLOWED_ROLES = {"EMERGENCY_OPERATOR", "AUTHORIZED_OFFICIAL", "CONTROLLER", "SUPER_ADMIN", "ADMIN"}

INCIDENT_TYPES = [
    "ACCIDENT", "DERAILMENT_RELATED", "TRACK_FAILURE", "SIGNAL_FAILURE",
    "OHE_FAILURE", "OBSTRUCTION", "PERSON_ON_TRACK", "SUSPECTED_SUICIDE",
    "RAIL_FRACTURE", "SIGNAL_BLANKING", "OHE_BREAKDOWN", "BOULDER_FALL",
    "LEVEL_CROSSING_GATE_FAILURE", "TRACK_OBSTRUCTION", "EQUIPMENT_MALFUNCTION", "OTHER_EMERGENCY"
]

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
# Matches DB enum incident_response_status (authoritative): OPEN, IN_PROGRESS, CLEARED
RESPONSE_STATUSES = ["OPEN", "IN_PROGRESS", "CLEARED"]
# Matches DB enum emergency_response_status for EmergencyResponse.status updates
EMERGENCY_RESPONSE_STATUSES = ["ALERT_RECEIVED", "TEAM_DISPATCHED", "TEAM_ARRIVED", "INCIDENT_HANDED_OVER", "AREA_CLEARED"]
INCIDENT_STATUSES = [
    "REPORTED", "ACKNOWLEDGED", "ASSESSED", "EMERGENCY_PLANNING", "AWAITING_OFFICIAL_DECISION",
    "APPROVED", "RESPONSE_DISPATCHED", "ON_SITE", "WORK_IN_PROGRESS", "CLEARANCE_PENDING",
    "CLEARED", "RELEASED", "INCIDENT_CLOSED", "REJECTED"
]
AUTHORITY_TYPES = [
    "RAILWAY", "RAILWAY_PROTECTION_FORCE", "GOVERNMENT_RAILWAY_POLICE", "LOCAL_POLICE",
    "FIRE_BRIGADE", "NDRF", "MEDICAL", "DISTRICT_ADMINISTRATION", "OTHER"
]

service = EmergencyService()


def _check_access(current_user: User):
    if current_user.role not in ALLOWED_ROLES and "OFFICIAL" not in (current_user.role or ""):
        raise HTTPException(status_code=403, detail="Emergency access restricted to authorized roles")


def _serialize_incident(inc: Incident) -> Dict[str, Any]:
    return {
        "id": inc.id,
        "incident_code": inc.incident_code,
        "incident_type": inc.incident_type,
        "severity": inc.severity,
        "description": inc.description,
        "section_id": inc.section_id,
        "section_name": inc.section.name if inc.section else None,
        "track_id": inc.track_id,
        "track_number": inc.track.track_code if inc.track else None,
        "track_code": inc.track.track_code if inc.track else None,
        "asset_id": inc.asset_id,
        "latitude": float(inc.latitude) if inc.latitude is not None else None,
        "longitude": float(inc.longitude) if inc.longitude is not None else None,
        "status": inc.status,
        "response_status": inc.response_status,
        "reported_at": inc.reported_at.isoformat() if inc.reported_at else None,
        "reported_by": inc.reported_by,
        "reporter_name": inc.reporter.name if inc.reporter else None,
        "railway_alert_status": inc.railway_alert_status,
        "police_alert_status": inc.police_alert_status,
        "acknowledged_at": inc.acknowledged_at.isoformat() if inc.acknowledged_at else None,
        "acknowledged_by": inc.acknowledged_by,
        "assessed_at": inc.assessed_at.isoformat() if inc.assessed_at else None,
        "assessed_by": inc.assessed_by,
        "assessment_notes": inc.assessment_notes,
        "block_request_id": inc.block_request_id,
        "block_code": inc.block_request.block_code if inc.block_request else None,
        "selected_optimized_block_id": inc.selected_optimized_block_id,
        "clearance_time": inc.clearance_time.isoformat() if inc.clearance_time else None,
        "cleared_at": inc.cleared_at.isoformat() if inc.cleared_at else None,
        "cleared_by": inc.cleared_by,
        "clearance_notes": inc.clearance_notes,
        "closed_at": inc.closed_at.isoformat() if inc.closed_at else None,
        "closed_by": inc.closed_by,
        "is_simulated": inc.is_simulated,
        "responses": [
            {
                "id": r.id,
                "authority_type": r.authority_type,
                "authority_name": r.authority_name,
                "team_name": r.team_name,
                "notification_time": r.notification_time.isoformat() if r.notification_time else None,
                "acknowledgement_time": r.acknowledgement_time.isoformat() if r.acknowledgement_time else None,
                "arrival_time": r.arrival_time.isoformat() if r.arrival_time else None,
                "work_start_time": r.work_start_time.isoformat() if r.work_start_time else None,
                "completion_time": r.completion_time.isoformat() if r.completion_time else None,
                "clearance_time": r.clearance_time.isoformat() if r.clearance_time else None,
                "status": r.status,
                "notes": r.notes,
                "assigned_resources": r.assigned_resources,
            } for r in (inc.responses or [])
        ],
    }


# ── Schemas ──

class IncidentCreate(BaseModel):
    incident_type: str
    severity: str = "HIGH"
    description: Optional[str] = None
    section_id: Optional[int] = None
    track_id: Optional[int] = None
    asset_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_simulated: Optional[bool] = False

    @field_validator('incident_type')
    @classmethod
    def validate_incident_type(cls, v: str) -> str:
        if v not in INCIDENT_TYPES:
            raise ValueError(f"Invalid incident_type '{v}'. Valid: {INCIDENT_TYPES}")
        return v

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in SEVERITIES:
            raise ValueError(f"Invalid severity '{v}'. Valid: {SEVERITIES}")
        return v

class IncidentAssess(BaseModel):
    assessment_notes: Optional[str] = None
    notes: Optional[str] = None
    severity: Optional[str] = None
    estimated_duration_mins: Optional[int] = 120
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    department_id: Optional[int] = None
    asset_id: Optional[int] = None

class OfficialDecision(BaseModel):
    decision: str = "APPROVE"  # APPROVE, MODIFY, REJECT
    team_name: Optional[str] = "Rapid Emergency Response Team"
    assigned_resources: Optional[str] = "ART-01, TWR-03, P-Way Gang"
    remarks: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None

class DispatchPayload(BaseModel):
    team_name: Optional[str] = "Rapid Emergency Restoration Gang"
    assigned_resources: Optional[str] = "Breakdown Crane, OHE Car, Track Tools"

class ClearancePayload(BaseModel):
    track_inspected: bool = True
    ohe_tested: bool = True
    signals_normal: bool = True
    notes: Optional[str] = "Track physically verified clear, OHE charged and signals normal."

class ClosePayload(BaseModel):
    notes: Optional[str] = "Incident closed after successful restoration and traffic normalization."


# ── Core Endpoints ──

@router.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = service.create_incident(db, payload.model_dump(), user_id=current_user.id)
    return _serialize_incident(inc)


@router.get("/incidents")
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    section_id: Optional[int] = None,
    is_simulated: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    items = service.list_incidents(
        db, status=status, severity=severity, section_id=section_id, is_simulated=is_simulated
    )
    return [_serialize_incident(i) for i in items]


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = service.get_incident_detail(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(inc)


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.acknowledge_incident(db, incident_id, user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/assess")
def assess_incident(
    incident_id: int,
    payload: IncidentAssess,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.assess_incident(db, incident_id, payload.model_dump(), user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents/{incident_id}/affected-trains")
def get_affected_trains(
    incident_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        return service.get_affected_trains(db, incident_id, start_time, end_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents/{incident_id}/conflicting-blocks")
def get_conflicting_blocks(
    incident_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        return service.get_conflicting_blocks(db, incident_id, start_time, end_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents/{incident_id}/resources")
def get_emergency_resources(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    return service.get_emergency_resources(db, incident_id)


@router.post("/incidents/{incident_id}/generate-candidates")
def generate_candidates(
    incident_id: int,
    duration_mins: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        candidates = service.generate_emergency_candidates(
            db, incident_id, user_id=current_user.id, duration_mins=duration_mins
        )
        return {"incident_id": incident_id, "candidates": candidates, "total": len(candidates)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/optimize")
def optimize_emergency(
    incident_id: int,
    simulation: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        return service.run_emergency_optimization(
            db, incident_id, user_id=current_user.id, simulation=simulation
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents/{incident_id}/recommendation")
def get_emergency_recommendation(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not inc.selected_optimized_block_id:
        return {"has_recommendation": False, "message": "No emergency block optimized yet"}

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == inc.selected_optimized_block_id).first()
    comparison = build_candidate_comparison_matrix(inc.block_request_id, db) if inc.block_request_id else []

    return {
        "has_recommendation": True,
        "optimized_block": {
            "id": ob.id,
            "block_code": ob.block_code,
            "start_time": ob.start_time.isoformat(),
            "end_time": ob.end_time.isoformat(),
            "total_duration_mins": ob.total_duration_mins,
            "total_delay_mins": ob.total_delay_mins,
            "affected_train_count": ob.affected_train_count,
            "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
            "recommendation_reason": ob.recommendation_reason,
            "status": ob.status,
        },
        "comparison_matrix": comparison,
    }


# ── Railway Authorized Official Decision Endpoints (Strict RBAC) ──

@router.post("/incidents/{incident_id}/approve")
def approve_emergency_block(
    incident_id: int,
    payload: OfficialDecision,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return service.official_approve(db, incident_id, payload.model_dump(), current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/modify")
def modify_emergency_block(
    incident_id: int,
    payload: OfficialDecision,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return service.official_modify(db, incident_id, payload.model_dump(), current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/reject")
def reject_emergency_block(
    incident_id: int,
    payload: OfficialDecision,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return service.official_reject(db, incident_id, payload.model_dump(), current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Response Dispatch & Tracking Lifecycle Endpoints ──

@router.post("/incidents/{incident_id}/dispatch")
def dispatch_response(
    incident_id: int,
    payload: Optional[DispatchPayload] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.dispatch_response(
            db, incident_id, dispatch_data=payload.model_dump() if payload else None, user_id=current_user.id
        )
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/arrive")
def record_arrival(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.record_arrival(db, incident_id, user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/start-work")
def start_work(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.start_work(db, incident_id, user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/request-clearance")
def request_clearance(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.request_clearance(db, incident_id, user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/grant-clearance")
def grant_clearance(
    incident_id: int,
    payload: ClearancePayload,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.grant_track_clearance(db, incident_id, payload.model_dump(), user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/release-block")
def release_emergency_block(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.release_emergency_block(db, incident_id, user_id=current_user.id)
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/incidents/{incident_id}/close")
def close_incident(
    incident_id: int,
    payload: Optional[ClosePayload] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    try:
        inc = service.close_incident(
            db, incident_id, closure_data=payload.model_dump() if payload else None, user_id=current_user.id
        )
        return _serialize_incident(inc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kpis")
def get_emergency_kpis(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    total = db.query(Incident).count()
    active = db.query(Incident).filter(Incident.status.notin_(["INCIDENT_CLOSED", "CLEARED", "RELEASED"])).count()
    planning = db.query(Incident).filter(Incident.status.in_(["ASSESSED", "EMERGENCY_PLANNING"])).count()
    awaiting_decision = db.query(Incident).filter(Incident.status == "AWAITING_OFFICIAL_DECISION").count()
    approved = db.query(Incident).filter(Incident.status == "APPROVED").count()
    in_progress = db.query(Incident).filter(Incident.status.in_(["RESPONSE_DISPATCHED", "ON_SITE", "WORK_IN_PROGRESS", "CLEARANCE_PENDING"])).count()
    cleared = db.query(Incident).filter(Incident.status.in_(["CLEARED", "RELEASED"])).count()
    closed = db.query(Incident).filter(Incident.status == "INCIDENT_CLOSED").count()

    return {
        "total_incidents": total,
        "active_incidents": active,
        "in_planning": planning,
        "awaiting_official_decision": awaiting_decision,
        "approved": approved,
        "work_in_progress": in_progress,
        "cleared_or_released": cleared,
        "closed": closed,
    }


# Backwards compatibility stats endpoint
@router.get("/stats")
def emergency_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return get_emergency_kpis(current_user=current_user, db=db)
