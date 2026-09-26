import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User
from app.models.department import Department
from app.models.railway import RailwaySection, Track
from app.models.incident import Incident, EmergencyResponse
from app.models.block import BlockRequest, BlockCandidate, OptimizedBlock
from app.models.maintenance import MaintenanceRequest
from app.services.emergency_service import EmergencyService

client = TestClient(app)
service = EmergencyService()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_token_for_user(db: Session, email: str) -> str:
    user = db.query(User).filter(User.email == email).first()
    assert user is not None, f"User {email} not found"
    dept = db.query(Department).filter(Department.id == user.department_id).first()
    dept_code = dept.code if dept else "ENG"
    return create_access_token(data={"sub": str(user.id), "user_id": user.id, "email": user.email, "role": user.role, "department_code": dept_code})


def auth_header(db: Session, email: str) -> dict:
    return {"Authorization": f"Bearer {get_token_for_user(db, email)}"}


@pytest.fixture
def test_setup(db: Session):
    # Ensure departments
    railway_dept = db.query(Department).filter(Department.code == "RAILWAY").first()
    if not railway_dept:
        railway_dept = Department(name="Railway Board / Operations", code="RAILWAY", description="Railway Authority")
        db.add(railway_dept)
        db.commit()
        db.refresh(railway_dept)

    eng_dept = db.query(Department).filter(Department.code == "ENG").first()
    if not eng_dept:
        eng_dept = Department(name="Engineering (P-Way)", code="ENG", description="Track Maintenance")
        db.add(eng_dept)
        db.commit()
        db.refresh(eng_dept)

    # Ensure Railway Official user
    official_user = db.query(User).filter(User.email == "official@railway.gov.in").first()
    if not official_user:
        official_user = User(
            email="official@railway.gov.in",
            name="Chief Operating Manager (Railway Official)",
            password_hash="mock_hashed_password",
            role="AUTHORIZED_OFFICIAL",
            department_id=railway_dept.id,
            is_active=True,
        )
        db.add(official_user)
        db.commit()
        db.refresh(official_user)

    # Ensure Emergency Operator user
    emergency_dept = db.query(Department).filter(Department.code == "EMERGENCY").first()
    operator_user = db.query(User).filter(User.email == "operator@railway.gov.in").first()
    if not operator_user:
        operator_user = User(
            email="operator@railway.gov.in",
            name="Emergency Response Operator",
            password_hash="mock_hashed_password",
            role="EMERGENCY_OPERATOR",
            department_id=emergency_dept.id if emergency_dept else 7,
            is_active=True,
        )
        db.add(operator_user)
        db.commit()
        db.refresh(operator_user)

    # Ensure Section & Track
    sec = db.query(RailwaySection).first()
    track = db.query(Track).first()

    return {
        "official": official_user,
        "operator": operator_user,
        "section": sec,
        "track": track,
    }


# ── TEST 1: Create Emergency Incident ──
def test_create_incident(db: Session, test_setup):
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "incident_type": "RAIL_FRACTURE",
        "severity": "CRITICAL",
        "description": "Severe rail fracture detected on Up line KM 142/6",
        "section_id": test_setup["section"].id if test_setup["section"] else 1,
        "track_id": test_setup["track"].id if test_setup["track"] else 1,
        "latitude": 17.4399,
        "longitude": 78.4983,
        "is_simulated": False,
    }
    response = client.post("/api/emergency/incidents", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_code"].startswith("INC-")
    assert data["incident_type"] == "RAIL_FRACTURE"
    assert data["severity"] == "CRITICAL"
    assert data["status"] == "REPORTED"
    assert data["railway_alert_status"] == "SENT"


# ── TEST 2: List Incidents with Filters ──
def test_list_incidents(db: Session, test_setup):
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get("/api/emergency/incidents?severity=CRITICAL", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) > 0


# ── TEST 3: Get Incident Detail ──
def test_get_incident_detail(db: Session, test_setup):
    inc = db.query(Incident).first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get(f"/api/emergency/incidents/{inc.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == inc.id
    assert data["incident_code"] == inc.incident_code


# ── TEST 4: Acknowledge Incident ──
def test_acknowledge_incident(db: Session, test_setup):
    sec_id = test_setup["section"].id if test_setup["section"] else 1
    trk_id = test_setup["track"].id if test_setup["track"] else 1
    inc = db.query(Incident).filter(Incident.status == "REPORTED").first()
    if not inc:
        inc = service.create_incident(db, {"incident_type": "TRACK_OBSTRUCTION", "severity": "HIGH", "section_id": sec_id, "track_id": trk_id}, test_setup["operator"].id)
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/acknowledge", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledged_at"] is not None


# ── TEST 5: Assess Incident & Generate Maintenance/Block Request ──
def test_assess_incident(db: Session, test_setup):
    sec_id = test_setup["section"].id if test_setup["section"] else 1
    trk_id = test_setup["track"].id if test_setup["track"] else 1
    inc = db.query(Incident).filter(Incident.status.in_(["REPORTED", "ACKNOWLEDGED"])).first()
    if not inc:
        inc = service.create_incident(db, {"incident_type": "OHE_BREAKDOWN", "severity": "CRITICAL", "section_id": sec_id, "track_id": trk_id}, test_setup["operator"].id)
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "assessment_notes": "OHE wire snapped due to lightning strike; requires tower wagon isolation.",
        "estimated_duration_mins": 90,
        "severity": "CRITICAL",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/assess", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "EMERGENCY_PLANNING"
    assert data["block_request_id"] is not None
    assert data["block_code"].startswith("EMG-BLK-")


# ── TEST 6: Affected Trains Impact Query ──
def test_get_affected_trains(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "EMERGENCY_PLANNING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get(f"/api/emergency/incidents/{inc.id}/affected-trains", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "affected_train_count" in data
    assert "total_predicted_delay_minutes" in data
    assert "individual_predictions" in data


# ── TEST 7: Conflicting Blocks Query ──
def test_get_conflicting_blocks(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "EMERGENCY_PLANNING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get(f"/api/emergency/incidents/{inc.id}/conflicting-blocks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ── TEST 8: Emergency Resources Query ──
def test_get_emergency_resources(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "EMERGENCY_PLANNING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get(f"/api/emergency/incidents/{inc.id}/resources", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    assert any(r["resource_type"] == "ACCIDENT_RELIEF_TRAIN" for r in data)


# ── TEST 9: Generate Candidates & Safety Gate Validation ──
def test_generate_emergency_candidates(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "EMERGENCY_PLANNING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/generate-candidates", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    for cand in data["candidates"]:
        assert cand["safety_status"] in ("SAFE", "FEASIBLE")
        assert "is_safe_for_optimization" in cand


# ── TEST 10: Run OR-Tools Emergency CP-SAT Optimization ──
def test_run_emergency_optimization(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "EMERGENCY_PLANNING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/optimize", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("OPTIMAL", "FEASIBLE")
    assert data["optimized_block_id"] is not None
    assert "comparison_matrix" in data

    # Verify incident status transition to AWAITING_OFFICIAL_DECISION
    db.refresh(inc)
    assert inc.status == "AWAITING_OFFICIAL_DECISION"


# ── TEST 11: Get Recommendation & Comparison Matrix ──
def test_get_emergency_recommendation(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "AWAITING_OFFICIAL_DECISION").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get(f"/api/emergency/incidents/{inc.id}/recommendation", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["has_recommendation"] is True
    assert data["optimized_block"]["id"] is not None
    assert len(data["comparison_matrix"]) > 0


# ── TEST 12: Strict RBAC - Operator Denied Official Approval ──
def test_rbac_approval_denied_for_operator(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "AWAITING_OFFICIAL_DECISION").first()
    assert inc is not None
    operator_headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "decision": "APPROVE",
        "remarks": "Attempted approval by Operator",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/approve", json=payload, headers=operator_headers)
    assert response.status_code == 403
    assert "Only authenticated Railway Authorized Officials can approve" in response.json()["detail"]


# ── TEST 13: Strict RBAC - Authorized Official Approves Recommendation ──
def test_official_approve_success(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "AWAITING_OFFICIAL_DECISION").first()
    assert inc is not None
    official_headers = auth_header(db, test_setup["official"].email)
    payload = {
        "decision": "APPROVE",
        "team_name": "Rapid Breakdown Gang #1",
        "assigned_resources": "ART-01, TWR-03, P-Way Gang",
        "remarks": "Approved by COM for immediate restorative block.",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/approve", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["incident_status"] == "APPROVED"
    assert data["emergency_response_id"] is not None

    db.refresh(inc)
    assert inc.status == "APPROVED"


# ── TEST 14: Official Decision - Modify & Approve ──
def test_official_modify_decision(db: Session, test_setup):
    sec_id = test_setup["section"].id if test_setup["section"] else 1
    trk_id = test_setup["track"].id if test_setup["track"] else 1
    # Setup another incident for modify test
    inc2 = service.create_incident(db, {"incident_type": "SIGNAL_FAILURE", "severity": "HIGH", "section_id": sec_id, "track_id": trk_id}, test_setup["operator"].id)
    service.acknowledge_incident(db, inc2.id, test_setup["operator"].id)
    service.assess_incident(db, inc2.id, {"estimated_duration_mins": 60, "notes": "Signal head damaged"}, test_setup["operator"].id)
    service.generate_emergency_candidates(db, inc2.id, test_setup["operator"].id)
    service.run_emergency_optimization(db, inc2.id, test_setup["operator"].id)

    official_headers = auth_header(db, test_setup["official"].email)
    now = datetime.now(timezone.utc)
    payload = {
        "decision": "MODIFY",
        "start_time": (now + timedelta(minutes=10)).isoformat(),
        "end_time": (now + timedelta(minutes=80)).isoformat(),
        "team_name": "Signal & Interlocking Gang #2",
        "assigned_resources": "Signal Van, Test Kits",
        "remarks": "Extended window by 10 mins for safety testing.",
    }
    response = client.post(f"/api/emergency/incidents/{inc2.id}/modify", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["incident_status"] == "APPROVED"


# ── TEST 15: Official Decision - Reject ──
def test_official_reject_decision(db: Session, test_setup):
    sec_id = test_setup["section"].id if test_setup["section"] else 1
    trk_id = test_setup["track"].id if test_setup["track"] else 1
    # Setup another incident for reject test
    inc3 = service.create_incident(db, {"incident_type": "BOULDER_FALL", "severity": "HIGH", "section_id": sec_id, "track_id": trk_id}, test_setup["operator"].id)
    service.acknowledge_incident(db, inc3.id, test_setup["operator"].id)
    service.assess_incident(db, inc3.id, {"estimated_duration_mins": 120, "notes": "Boulder on hillside track"}, test_setup["operator"].id)
    service.generate_emergency_candidates(db, inc3.id, test_setup["operator"].id)
    service.run_emergency_optimization(db, inc3.id, test_setup["operator"].id)

    official_headers = auth_header(db, test_setup["official"].email)
    payload = {
        "decision": "REJECT",
        "reason": "Wait for geological safety clearance before heavy machinery deployment.",
    }
    response = client.post(f"/api/emergency/incidents/{inc3.id}/reject", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["incident_status"] == "ASSESSED"


# ── TEST 16: Dispatch Response ──
def test_dispatch_response(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "APPROVED").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "team_name": "Specialized Track Breakdown Gang",
        "assigned_resources": "Breakdown Crane, Heavy Jacks, Welding Kits",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/dispatch", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESPONSE_DISPATCHED"


# ── TEST 17: Record Response Arrival On-Site ──
def test_record_arrival(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "RESPONSE_DISPATCHED").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/arrive", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ON_SITE"


# ── TEST 18: Start Work ──
def test_start_work(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "ON_SITE").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/start-work", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "WORK_IN_PROGRESS"


# ── TEST 19: Request Track Clearance ──
def test_request_clearance(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "WORK_IN_PROGRESS").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/request-clearance", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CLEARANCE_PENDING"


# ── TEST 20: Track Clearance Fails If Mandatory Checklist Incomplete ──
def test_clearance_fails_if_unchecked(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "CLEARANCE_PENDING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "track_inspected": True,
        "ohe_tested": False,  # Failing check
        "signals_normal": True,
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/grant-clearance", json=payload, headers=headers)
    assert response.status_code == 400
    assert "All mandatory safety clearance checklist items" in response.json()["detail"]


# ── TEST 21: Grant Track Clearance Success ──
def test_grant_clearance_success(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "CLEARANCE_PENDING").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "track_inspected": True,
        "ohe_tested": True,
        "signals_normal": True,
        "notes": "Track verified safe, OHE 25kV charged, all color signals displaying clear aspects.",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/grant-clearance", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CLEARED"
    assert data["cleared_at"] is not None


# ── TEST 22: Release Emergency Block & Restore Section ──
def test_release_emergency_block(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "CLEARED").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    response = client.post(f"/api/emergency/incidents/{inc.id}/release-block", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RELEASED"


# ── TEST 23: Close Incident ──
def test_close_incident(db: Session, test_setup):
    inc = db.query(Incident).filter(Incident.status == "RELEASED").first()
    assert inc is not None
    headers = auth_header(db, test_setup["operator"].email)
    payload = {
        "notes": "Emergency restoration completed with zero residual hazards. Regular timetable traffic resumed.",
    }
    response = client.post(f"/api/emergency/incidents/{inc.id}/close", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INCIDENT_CLOSED"
    assert data["response_status"] == "CLOSED"
    assert data["closed_at"] is not None


# ── TEST 24: Emergency KPIs Endpoint ──
def test_get_emergency_kpis(db: Session, test_setup):
    headers = auth_header(db, test_setup["operator"].email)
    response = client.get("/api/emergency/kpis", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "active_incidents" in data
    assert "in_planning" in data
    assert "awaiting_official_decision" in data
    assert "approved" in data
    assert "work_in_progress" in data
    assert "cleared_or_released" in data
    assert "closed" in data
