from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.incident import Incident, EmergencyResponse

router = APIRouter(prefix="/api/emergency", tags=["emergency"])

ALLOWED_ROLES = {"EMERGENCY_OPERATOR", "AUTHORIZED_OFFICIAL", "CONTROLLER"}

INCIDENT_TYPES = [
    "ACCIDENT", "DERAILMENT_RELATED", "TRACK_FAILURE", "SIGNAL_FAILURE",
    "OHE_FAILURE", "OBSTRUCTION", "PERSON_ON_TRACK", "SUSPECTED_SUICIDE",
    "OTHER_EMERGENCY",
]

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
# Matches DB enum incident_response_status (authoritative): OPEN, IN_PROGRESS, CLEARED
RESPONSE_STATUSES = ["OPEN", "IN_PROGRESS", "CLEARED"]
# Matches DB enum emergency_response_status for EmergencyResponse.status updates
EMERGENCY_RESPONSE_STATUSES = ["ALERT_RECEIVED", "TEAM_DISPATCHED", "TEAM_ARRIVED", "INCIDENT_HANDED_OVER", "AREA_CLEARED"]
AUTHORITY_TYPES = ["RAILWAY_PROTECTION_FORCE", "GOVERNMENT_RAILWAY_POLICE", "LOCAL_POLICE",
                   "FIRE_BRIGADE", "NDRF", "MEDICAL", "DISTRICT_ADMINISTRATION", "OTHER"]


def _check_access(current_user: User):
    if current_user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Emergency access restricted to authorized roles")


def _audit(db: Session, user_id: int, action: str, entity_type: str, entity_id: int, details: str = ""):
    from app.models.audit import AuditLog
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=details,
    ))
    db.commit()


def _gen_incident_code(db: Session) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"INC-{today}-"
    last = db.query(Incident).filter(Incident.incident_code.like(f"{prefix}%")).count()
    return f"{prefix}{last + 1:04d}"


# ── Schemas ──

class IncidentCreate(BaseModel):
    incident_type: str
    severity: str = "HIGH"
    description: Optional[str] = None
    section_id: Optional[int] = None
    track_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class IncidentUpdate(BaseModel):
    severity: Optional[str] = None
    description: Optional[str] = None
    response_status: Optional[str] = None
    railway_alert_status: Optional[str] = None
    police_alert_status: Optional[str] = None
    clearance_time: Optional[datetime] = None

class ResponseCreate(BaseModel):
    authority_type: str
    authority_name: Optional[str] = None
    notes: Optional[str] = None

class ResponseUpdate(BaseModel):
    acknowledgement_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    clearance_time: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Incident Endpoints ──

@router.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    if payload.incident_type not in INCIDENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid incident_type. Valid: {INCIDENT_TYPES}")
    if payload.severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {SEVERITIES}")

    code = _gen_incident_code(db)
    geom = None
    if payload.latitude is not None and payload.longitude is not None:
        geom = func.ST_SetSRID(func.ST_MakePoint(payload.longitude, payload.latitude), 4326)

    inc = Incident(
        incident_code=code,
        incident_type=payload.incident_type,
        severity=payload.severity,
        description=payload.description,
        section_id=payload.section_id,
        track_id=payload.track_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location=geom,
        reported_by=current_user.id,
        response_status="OPEN",
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)

    _audit(db, current_user.id, "INCIDENT_CREATE", "incident", inc.id, f"Created incident {code}")

    return {
        "id": inc.id,
        "incident_code": inc.incident_code,
        "incident_type": inc.incident_type,
        "severity": inc.severity,
        "response_status": inc.response_status,
        "reported_at": inc.reported_at.isoformat() if inc.reported_at else None,
    }


@router.get("/incidents")
def list_incidents(
    skip: int = 0,
    limit: int = 50,
    severity: Optional[str] = None,
    response_status: Optional[str] = None,
    incident_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    q = db.query(Incident)
    if severity:
        q = q.filter(Incident.severity == severity)
    if response_status:
        q = q.filter(Incident.response_status == response_status)
    if incident_type:
        q = q.filter(Incident.incident_type == incident_type)
    total = q.count()
    items = q.order_by(Incident.reported_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": i.id,
                "incident_code": i.incident_code,
                "incident_type": i.incident_type,
                "severity": i.severity,
                "response_status": i.response_status,
                "section_id": i.section_id,
                "latitude": float(i.latitude) if i.latitude else None,
                "longitude": float(i.longitude) if i.longitude else None,
                "reported_at": i.reported_at.isoformat() if i.reported_at else None,
                "reported_by": i.reported_by,
                "railway_alert_status": i.railway_alert_status,
                "police_alert_status": i.police_alert_status,
                "clearance_time": i.clearance_time.isoformat() if i.clearance_time else None,
            } for i in items
        ],
        "skip": skip,
        "limit": limit,
    }


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    responses = db.query(EmergencyResponse).filter(EmergencyResponse.incident_id == inc.id).order_by(EmergencyResponse.created_at.desc()).all()

    return {
        "id": inc.id,
        "incident_code": inc.incident_code,
        "incident_type": inc.incident_type,
        "severity": inc.severity,
        "description": inc.description,
        "section_id": inc.section_id,
        "track_id": inc.track_id,
        "latitude": float(inc.latitude) if inc.latitude else None,
        "longitude": float(inc.longitude) if inc.longitude else None,
        "reported_at": inc.reported_at.isoformat() if inc.reported_at else None,
        "reported_by": inc.reported_by,
        "railway_alert_status": inc.railway_alert_status,
        "police_alert_status": inc.police_alert_status,
        "response_status": inc.response_status,
        "clearance_time": inc.clearance_time.isoformat() if inc.clearance_time else None,
        "responses": [
            {
                "id": r.id,
                "authority_type": r.authority_type,
                "authority_name": r.authority_name,
                "notification_time": r.notification_time.isoformat() if r.notification_time else None,
                "acknowledgement_time": r.acknowledgement_time.isoformat() if r.acknowledgement_time else None,
                "arrival_time": r.arrival_time.isoformat() if r.arrival_time else None,
                "clearance_time": r.clearance_time.isoformat() if r.clearance_time else None,
                "status": r.status,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in responses
        ],
    }


@router.patch("/incidents/{incident_id}")
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if payload.severity and payload.severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {SEVERITIES}")
    if payload.response_status and payload.response_status not in RESPONSE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid response_status. Valid: {RESPONSE_STATUSES}")

    if payload.severity is not None:
        inc.severity = payload.severity
    if payload.description is not None:
        inc.description = payload.description
    if payload.response_status is not None:
        inc.response_status = payload.response_status
    if payload.railway_alert_status is not None:
        inc.railway_alert_status = payload.railway_alert_status
    if payload.police_alert_status is not None:
        inc.police_alert_status = payload.police_alert_status
    if payload.clearance_time is not None:
        inc.clearance_time = payload.clearance_time

    db.commit()
    _audit(db, current_user.id, "INCIDENT_UPDATE", "incident", inc.id, f"Updated incident {inc.incident_code}")

    return {"id": inc.id, "incident_code": inc.incident_code, "response_status": inc.response_status}


# ── Emergency Response Endpoints ──

@router.post("/incidents/{incident_id}/responses", status_code=status.HTTP_201_CREATED)
def create_response(
    incident_id: int,
    payload: ResponseCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if payload.authority_type not in AUTHORITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid authority_type. Valid: {AUTHORITY_TYPES}")

    resp = EmergencyResponse(
        incident_id=incident_id,
        authority_type=payload.authority_type,
        authority_name=payload.authority_name,
        notification_time=datetime.now(timezone.utc),
        status="ALERT_RECEIVED",
        notes=payload.notes,
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)

    _audit(db, current_user.id, "RESPONSE_CREATE", "emergency_response", resp.id, f"Response for incident {inc.incident_code}")

    return {
        "id": resp.id,
        "incident_id": resp.incident_id,
        "authority_type": resp.authority_type,
        "status": resp.status,
        "notification_time": resp.notification_time.isoformat() if resp.notification_time else None,
    }


@router.patch("/responses/{response_id}")
def update_response(
    response_id: int,
    payload: ResponseUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    resp = db.query(EmergencyResponse).filter(EmergencyResponse.id == response_id).first()
    if not resp:
        raise HTTPException(status_code=404, detail="Response not found")

    if payload.status and payload.status not in EMERGENCY_RESPONSE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {EMERGENCY_RESPONSE_STATUSES}")

    if payload.acknowledgement_time is not None:
        resp.acknowledgement_time = payload.acknowledgement_time
    if payload.arrival_time is not None:
        resp.arrival_time = payload.arrival_time
    if payload.clearance_time is not None:
        resp.clearance_time = payload.clearance_time
    if payload.status is not None:
        resp.status = payload.status
    if payload.notes is not None:
        resp.notes = payload.notes

    db.commit()
    _audit(db, current_user.id, "RESPONSE_UPDATE", "emergency_response", resp.id, f"Updated response {resp.id}")

    return {"id": resp.id, "status": resp.status}


# ── Dashboard Stats ──

@router.get("/stats")
def emergency_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _check_access(current_user)
    total = db.query(Incident).count()
    open_count = db.query(Incident).filter(Incident.response_status.in_(["OPEN", "IN_PROGRESS"])).count()
    critical = db.query(Incident).filter(Incident.severity == "CRITICAL", Incident.response_status != "CLEARED").count()
    sections_affected = db.query(Incident.section_id).filter(Incident.section_id.isnot(None), Incident.response_status != "CLEARED").distinct().count()

    return {
        "total_incidents": total,
        "active_incidents": open_count,
        "critical_incidents": critical,
        "sections_affected": sections_affected,
    }
