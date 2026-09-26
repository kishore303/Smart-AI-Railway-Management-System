import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.department import Department
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction
from app.models.block import (
    BlockRequest,
    BlockCandidate,
    OptimizedBlock,
    OptimizedBlockSource,
    BlockIntegrationRequest,
    BlockAffectedTrain,
    BlockResourceAllocation,
)
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.optimizer.engine import optimize_block_request
from app.safety.engine import validate_candidate


client = TestClient(app)


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
    # Ensure standard railway official user exists
    railway_dept = db.query(Department).filter(Department.code == "RAILWAY").first()
    if not railway_dept:
        railway_dept = Department(name="Railway Board / Operations", code="RAILWAY", description="Railway Authority")
        db.add(railway_dept)
        db.commit()
        db.refresh(railway_dept)

    official = db.query(User).filter(User.email == "official@railway.gov.in").first()
    if not official:
        official = User(
            name="Railway Authorized Official",
            email="official@railway.gov.in",
            password_hash="dummy",
            role="AUTHORIZED_OFFICIAL",
            department_id=railway_dept.id,
            is_active=True,
        )
        db.add(official)
        db.commit()

    eng_dept = db.query(Department).filter(Department.code == "ENG").first()
    eng_staff = db.query(User).filter(User.email == "eng.staff@railway.gov.in").first()
    if not eng_staff:
        eng_staff = User(
            name="Engineering Staff",
            email="eng.staff@railway.gov.in",
            password_hash="dummy",
            role="MAINTENANCE_STAFF",
            department_id=eng_dept.id if eng_dept else 1,
            is_active=True,
        )
        db.add(eng_staff)
        db.commit()

    # Create verified maintenance request
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    mreq = MaintenanceRequest(
        request_code=f"MR-P8-{uid}",
        department_id=eng_dept.id if eng_dept else 1,
        asset_id=1,
        section_id=1,
        track_id=1,
        requested_by=eng_staff.id,
        maintenance_type="TRACK_MAINTENANCE",
        priority="HIGH",
        description="Phase 8 Approval Center Test Request",
        requested_start=now + timedelta(days=2),
        requested_end=now + timedelta(days=2, hours=4),
        requested_duration_mins=75,
        status="VERIFIED",
    )
    db.add(mreq)
    db.commit()
    db.refresh(mreq)

    # Create BlockRequest
    blk = BlockRequest(
        block_code=f"BLK-P8-{uid}",
        maintenance_request_id=mreq.id,
        section_id=1,
        track_id=1,
        requested_start=mreq.requested_start,
        requested_end=mreq.requested_end,
        block_type="MAINTENANCE",
        status="PROPOSED",
    )
    db.add(blk)
    db.commit()
    db.refresh(blk)

    # Create safe candidates
    c1 = BlockCandidate(
        block_request_id=blk.id,
        section_id=1,
        track_id=1,
        candidate_start=mreq.requested_start,
        candidate_end=mreq.requested_start + timedelta(minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=12,
        affected_train_count=1,
        safety_status="SAFE",
    )
    c2 = BlockCandidate(
        block_request_id=blk.id,
        section_id=1,
        track_id=1,
        candidate_start=mreq.requested_start + timedelta(hours=1),
        candidate_end=mreq.requested_start + timedelta(hours=1, minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=5,
        affected_train_count=1,
        safety_status="SAFE",
    )
    c_unsafe = BlockCandidate(
        block_request_id=blk.id,
        section_id=1,
        track_id=1,
        candidate_start=mreq.requested_start + timedelta(hours=2),
        candidate_end=mreq.requested_start + timedelta(hours=2, minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=2,
        affected_train_count=0,
        safety_status="UNSAFE",
        safety_rejection_reason="Existing conflicting block on track 1",
    )
    db.add_all([c1, c2, c_unsafe])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    db.refresh(c_unsafe)

    # Validate candidates with SafetyEngine
    sv1 = SafetyValidation(candidate_id=c1.id, block_request_id=blk.id, overall_status="SAFE", is_safe_for_optimization=True, checks={"track_conflict": "PASS", "duration_adequacy": "PASS"})
    sv2 = SafetyValidation(candidate_id=c2.id, block_request_id=blk.id, overall_status="SAFE", is_safe_for_optimization=True, checks={"track_conflict": "PASS", "duration_adequacy": "PASS"})
    sv3 = SafetyValidation(candidate_id=c_unsafe.id, block_request_id=blk.id, overall_status="UNSAFE", is_safe_for_optimization=False, checks={"track_conflict": "FAIL"}, rejection_reasons=["Track conflict"])
    db.add_all([sv1, sv2, sv3])
    db.commit()

    # Run optimization
    opt_res = optimize_block_request(blk.id, db, user_id=official.id)
    assert opt_res["status"] in ("OPTIMAL", "FEASIBLE")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == opt_res["optimized_block_id"]).first()
    assert ob is not None

    return {"mreq": mreq, "blk": blk, "ob": ob, "official": official, "staff": eng_staff}


def test_01_pending_approval_list_api(db: Session, test_setup):
    headers = auth_header(db, "official@railway.gov.in")
    res = client.get("/api/approval/pending", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    found = any(i["optimized_block_id"] == test_setup["ob"].id for i in items)
    assert found is True


def test_02_approval_details_12_sections_api(db: Session, test_setup):
    headers = auth_header(db, "official@railway.gov.in")
    ob_id = test_setup["ob"].id
    res = client.get(f"/api/approval/{ob_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Verify all 12 sections exist and contain valid fields
    assert "maintenance_request" in data
    assert data["maintenance_request"]["request_code"] == test_setup["mreq"].request_code

    assert "ownership" in data
    assert "primary_department" in data["ownership"]

    assert "asset" in data
    assert "asset_code" in data["asset"]

    assert "ai_predictions" in data
    assert "operational_risk" in data["ai_predictions"]
    assert "model_metadata" in data["ai_predictions"]
    assert data["ai_predictions"]["model_metadata"]["prediction_status"] == "VALID"

    assert "affected_trains" in data
    assert isinstance(data["affected_trains"], list)

    assert "safety_validation" in data
    assert data["safety_validation"]["overall_status"] == "SAFE"

    assert "candidate_comparison" in data
    assert "safe_alternatives" in data["candidate_comparison"]
    assert "rejected_candidates" in data["candidate_comparison"]

    assert "optimization" in data
    assert data["optimization"]["solver_status"] == "OPTIMAL"

    assert "cross_department" in data
    assert "resources" in data
    assert "map_context" in data
    assert "decision" in data
    assert data["is_eligible_for_approval"] is True


def test_03_positive_approval_workflow(db: Session, test_setup):
    headers = auth_header(db, "official@railway.gov.in")
    ob_id = test_setup["ob"].id

    payload = {"reason": "Approved by Railway Authorized Official following complete safety review."}
    res = client.post(f"/api/approval/{ob_id}/approve", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "APPROVED"
    assert data["new_status"] == "SCHEDULED"

    # Verify database state
    db.expire_all()
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == ob_id).first()
    assert ob.status == "SCHEDULED"
    assert ob.approved_by == test_setup["official"].id
    assert ob.approved_at is not None

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == test_setup["mreq"].id).first()
    assert mreq.status == "APPROVED"

    # Verify audit log
    audit = db.query(AuditLog).filter(AuditLog.entity_type == "optimized_block", AuditLog.entity_id == ob_id, AuditLog.action == "APPROVE_BLOCK").first()
    assert audit is not None
    assert audit.user_id == test_setup["official"].id

    # Verify notification
    notif = db.query(Notification).filter(Notification.optimized_block_id == ob_id, Notification.type == "BLOCK_APPROVED").first()
    assert notif is not None


def test_04_unauthorized_roles_cannot_approve(db: Session, test_setup):
    unauthorized_emails = [
        "eng.staff@railway.gov.in",
        "eng.je@railway.gov.in",
        "eng.sse@railway.gov.in",
        "ops.operator@railway.gov.in",
        "ctrl.controller@railway.gov.in",
    ]
    ob_id = test_setup["ob"].id

    for email in unauthorized_emails:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            continue
        headers = auth_header(db, email)
        res = client.post(f"/api/approval/{ob_id}/approve", json={"reason": "Unauthorized attempt"}, headers=headers)
        assert res.status_code == 403, f"Expected 403 for {email} ({u.role}), got {res.status_code}"


def test_05_unauthorized_departments_cannot_approve(db: Session, test_setup):
    # Engineering staff user attempting approval
    headers = auth_header(db, test_setup["staff"].email)
    res = client.post(f"/api/approval/{test_setup['ob'].id}/approve", json={"reason": "Bad dept attempt"}, headers=headers)
    assert res.status_code == 403
    assert "Department 'RAILWAY'" in res.json()["detail"]


def test_06_self_approval_protection(db: Session, test_setup):
    # Set maintenance request creator to the official itself
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == test_setup["mreq"].id).first()
    mreq.requested_by = test_setup["official"].id
    db.commit()

    # Attempt approval by same user
    headers = auth_header(db, "official@railway.gov.in")
    res = client.post(f"/api/approval/{test_setup['ob'].id}/approve", json={"reason": "Self approve attempt"}, headers=headers)
    assert res.status_code == 403
    assert "Self-approval prohibited" in res.json()["detail"]

    # Revert requested_by
    mreq.requested_by = test_setup["staff"].id
    db.commit()


def test_07_stale_optimization_conflicting_block(db: Session, test_setup):
    ob = test_setup["ob"]
    now = datetime.now(timezone.utc)

    # Create overlapping block request created AFTER the optimized block
    conflict_blk = BlockRequest(
        block_code=f"BLK-CONFLICT-{uuid.uuid4().hex[:8]}",
        maintenance_request_id=test_setup["mreq"].id,
        section_id=ob.section_id,
        track_id=ob.track_id,
        requested_start=ob.start_time,
        requested_end=ob.end_time,
        block_type="MAINTENANCE",
        status="REQUESTED",
        created_at=now + timedelta(seconds=10),
    )
    db.add(conflict_blk)
    db.commit()

    headers = auth_header(db, "official@railway.gov.in")
    res = client.post(f"/api/approval/{ob.id}/approve", json={"reason": "Stale approval attempt"}, headers=headers)
    assert res.status_code == 409
    assert "re-optimization required" in res.json()["detail"]

    # Clean up conflict
    db.delete(conflict_blk)
    db.commit()


def test_08_unsafe_candidate_approval_prevented(db: Session, test_setup):
    ob = test_setup["ob"]
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        cand = db.query(BlockCandidate).filter(BlockCandidate.is_selected == True).first()

    # Temporarily invalidate safety
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
    sv.overall_status = "UNSAFE"
    sv.is_safe_for_optimization = False
    sv.rejection_reasons = ["Immediate track defect reported"]
    db.commit()

    headers = auth_header(db, "official@railway.gov.in")
    res = client.post(f"/api/approval/{ob.id}/approve", json={"reason": "Approve unsafe attempt"}, headers=headers)
    assert res.status_code == 409
    assert "safety" in res.json()["detail"].lower()

    # Revert
    sv.overall_status = "SAFE"
    sv.is_safe_for_optimization = True
    sv.rejection_reasons = []
    db.commit()


def test_09_modify_workflow_and_revalidation(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # Pick an alternative candidate
    cand2 = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == test_setup["blk"].id, BlockCandidate.safety_status == "SAFE").order_by(BlockCandidate.id.desc()).first()

    payload = {
        "new_candidate_id": cand2.id,
        "reason": "Operational request to switch to alternative safe window",
    }
    res = client.post(f"/api/approval/{ob.id}/modify", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "MODIFIED"
    assert data["new_status"] == "MODIFIED"
    assert data["requires_revalidation"] is True
    assert data["requires_reoptimization"] is True

    # Check database
    db.refresh(ob)
    assert ob.status == "MODIFIED"
    assert ob.optimization_score is None  # Invalidated old score


def test_10_reject_with_mandatory_reason(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    payload = {"reason": "Operational conflict with priority freight movement on Section S101"}
    res = client.post(f"/api/approval/{ob.id}/reject", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "REJECTED"
    assert data["new_status"] == "REJECTED"
    assert data["reason"] == payload["reason"]

    # Verify in DB
    db.refresh(ob)
    assert ob.status == "REJECTED"
    assert ob.rejection_reason == payload["reason"]


def test_11_reject_without_reason_rejected(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # Reset status to PROPOSED
    ob.status = "PROPOSED"
    db.commit()

    res = client.post(f"/api/approval/{ob.id}/reject", json={"reason": ""}, headers=headers)
    assert res.status_code == 422
    assert "mandatory rejection reason" in res.json()["detail"]


def test_12_double_approval_idempotency(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # First approve
    ob.status = "PROPOSED"
    db.commit()

    res1 = client.post(f"/api/approval/{ob.id}/approve", json={"reason": "First approval"}, headers=headers)
    assert res1.status_code == 200

    audit_count_1 = db.query(AuditLog).filter(AuditLog.entity_type == "optimized_block", AuditLog.entity_id == ob.id, AuditLog.action == "APPROVE_BLOCK").count()

    # Second approve (Idempotency test)
    res2 = client.post(f"/api/approval/{ob.id}/approve", json={"reason": "Duplicate approval call"}, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["decision"] == "APPROVED"
    assert "Already approved" in data2["reason"]

    audit_count_2 = db.query(AuditLog).filter(AuditLog.entity_type == "optimized_block", AuditLog.entity_id == ob.id, AuditLog.action == "APPROVE_BLOCK").count()
    assert audit_count_2 == audit_count_1, "Duplicate audit logs should not be created on idempotent call"


def test_13_block_lifecycle_transitions(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # State 1: SCHEDULED
    ob.status = "SCHEDULED"
    db.commit()

    # State 2: SCHEDULED -> ACTIVE
    res_act = client.post(f"/api/blocks/{ob.id}/activate", json={"simulation": True}, headers=headers)
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIVE"

    # State 3: ACTIVE -> MAINTENANCE
    res_maint = client.post(f"/api/blocks/{ob.id}/maintenance", headers=headers)
    assert res_maint.status_code == 200
    assert res_maint.json()["status"] == "MAINTENANCE"

    # State 4: MAINTENANCE -> CLEARANCE_PENDING
    res_clr = client.post(f"/api/blocks/{ob.id}/clearance", headers=headers)
    assert res_clr.status_code == 200
    assert res_clr.json()["status"] == "CLEARANCE_PENDING"

    # State 5: CLEARANCE_PENDING -> RELEASED
    res_rel = client.post(f"/api/blocks/{ob.id}/release", headers=headers)
    assert res_rel.status_code == 200
    assert res_rel.json()["status"] == "RELEASED"

    # State 6: RELEASED -> COMPLETED
    res_comp = client.post(f"/api/blocks/{ob.id}/complete", headers=headers)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"


def test_14_invalid_state_transitions(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # REJECTED -> ACTIVE not allowed
    ob.status = "REJECTED"
    db.commit()

    res = client.post(f"/api/blocks/{ob.id}/activate", headers=headers)
    assert res.status_code == 409
    assert "Invalid state transition" in res.json()["detail"]

    # PROPOSED -> ACTIVE not allowed
    ob.status = "PROPOSED"
    db.commit()

    res2 = client.post(f"/api/blocks/{ob.id}/activate", headers=headers)
    assert res2.status_code == 409


def test_15_release_requires_clearance(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    # ACTIVE -> RELEASED directly without CLEARANCE_PENDING is rejected
    ob.status = "ACTIVE"
    db.commit()

    res = client.post(f"/api/blocks/{ob.id}/release", headers=headers)
    assert res.status_code == 409
    assert "Clearance check is mandatory" in res.json()["detail"]


def test_16_simulated_activation_flag(db: Session, test_setup):
    ob = test_setup["ob"]
    headers = auth_header(db, "official@railway.gov.in")

    ob.status = "SCHEDULED"
    db.commit()

    res = client.post(f"/api/blocks/{ob.id}/activate", json={"simulation": True}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "SIMULATION" in data["mode"]


def test_17_emergency_operator_cannot_approve(db: Session, test_setup):
    em_dept = db.query(Department).filter(Department.code == "EMERGENCY").first()
    em_op = db.query(User).filter(User.email == "em.operator@railway.gov.in").first()
    if not em_op:
        em_op = User(
            name="Emergency Operator",
            email="em.operator@railway.gov.in",
            password_hash="dummy",
            role="EMERGENCY_OPERATOR",
            department_id=em_dept.id if em_dept else 1,
            is_active=True,
        )
        db.add(em_op)
        db.commit()

    headers = auth_header(db, "em.operator@railway.gov.in")
    res = client.post(f"/api/approval/{test_setup['ob'].id}/approve", json={"reason": "Emergency operator attempt"}, headers=headers)
    assert res.status_code == 403


def test_18_approval_history_api(db: Session, test_setup):
    headers = auth_header(db, "official@railway.gov.in")
    res = client.get("/api/approval/history", headers=headers)
    assert res.status_code == 200
    history = res.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    assert "action" in history[0]
    assert "user_name" in history[0]


def test_19_model_traceability_no_internal_paths(db: Session, test_setup):
    headers = auth_header(db, "official@railway.gov.in")
    res = client.get(f"/api/approval/{test_setup['ob'].id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    meta = data["ai_predictions"]["model_metadata"]
    # Verify no raw paths leaked
    assert "C:\\" not in str(meta)
    assert "D:\\" not in str(meta)
    assert "/tmp" not in str(meta)
    assert meta["version"] == "v1.0"
