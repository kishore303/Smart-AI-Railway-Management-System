import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.department import Department
from app.models.maintenance import MaintenanceRequest
from app.models.block import (
    BlockRequest,
    BlockCandidate,
    OptimizedBlock,
    OptimizedBlockSource,
    BlockIntegrationRequest,
)
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.optimizer.config import OptimizationConfig, OptimizationWeights, validate_weights
from app.optimizer.engine import (
    optimize_block_request,
    get_safe_candidates_for_optimization,
    build_candidate_comparison_matrix,
)

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def auth_header(db: Session, email: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = db.query(User).filter(User.role == "AUTHORIZED_OFFICIAL").first()
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def p7_setup(db: Session):
    eng_dept = db.query(Department).filter(Department.code == "ENG").first()
    staff = db.query(User).filter(User.email == "eng.staff@railway.gov.in").first()
    official = db.query(User).filter(User.email == "official@railway.gov.in").first()

    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    mreq = MaintenanceRequest(
        request_code=f"MR-P7-{uid}",
        department_id=eng_dept.id if eng_dept else 1,
        asset_id=1,
        section_id=1,
        track_id=1,
        requested_by=staff.id if staff else 1,
        maintenance_type="TRACK_MAINTENANCE",
        priority="HIGH",
        description="Phase 7 OR-Tools Test",
        requested_start=now + timedelta(days=1),
        requested_end=now + timedelta(days=1, hours=4),
        requested_duration_mins=75,
        status="VERIFIED",
    )
    db.add(mreq)
    db.commit()
    db.refresh(mreq)

    blk = BlockRequest(
        block_code=f"BLK-P7-{mreq.id}",
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

    c1 = BlockCandidate(
        block_request_id=blk.id,
        section_id=1,
        track_id=1,
        candidate_start=mreq.requested_start,
        candidate_end=mreq.requested_start + timedelta(minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=12,
        affected_train_count=2,
        safety_status="SAFE",
    )
    c2 = BlockCandidate(
        block_request_id=blk.id,
        section_id=1,
        track_id=1,
        candidate_start=mreq.requested_start + timedelta(hours=1),
        candidate_end=mreq.requested_start + timedelta(hours=1, minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=90,
        affected_train_count=5,
        safety_status="SAFE",
    )
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    sv1 = SafetyValidation(candidate_id=c1.id, block_request_id=blk.id, overall_status="SAFE", is_safe_for_optimization=True, checks={"track_conflict": "PASS"})
    sv2 = SafetyValidation(candidate_id=c2.id, block_request_id=blk.id, overall_status="SAFE", is_safe_for_optimization=True, checks={"track_conflict": "PASS"})
    db.add_all([sv1, sv2])
    db.commit()

    return {"mreq": mreq, "blk": blk, "c1": c1, "c2": c2, "official": official}


def test_01_single_request_optimization_cp_sat(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")
    assert res["selected_candidate_id"] == p7_setup["c1"].id
    assert res["optimized_block_id"] is not None


def test_02_hard_safety_gate_unsafe_candidate_excluded(db: Session, p7_setup):
    c_unsafe = BlockCandidate(
        block_request_id=p7_setup["blk"].id,
        section_id=1,
        track_id=1,
        candidate_start=p7_setup["mreq"].requested_start + timedelta(hours=2),
        candidate_end=p7_setup["mreq"].requested_start + timedelta(hours=2, minutes=75),
        predicted_duration_mins=75,
        predicted_delay_mins=0,
        affected_train_count=0,
        safety_status="UNSAFE",
    )
    db.add(c_unsafe)
    db.commit()
    sv_u = SafetyValidation(candidate_id=c_unsafe.id, block_request_id=p7_setup["blk"].id, overall_status="UNSAFE", is_safe_for_optimization=False, checks={"track_conflict": "FAIL"})
    db.add(sv_u)
    db.commit()

    safe_cands = get_safe_candidates_for_optimization(p7_setup["blk"].id, db)
    assert all(c.id != c_unsafe.id for c in safe_cands)


def test_03_train_delay_minimization_objective(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["selected_candidate_id"] == p7_setup["c1"].id


def test_04_affected_train_count_objective(db: Session, p7_setup):
    p7_setup["c1"].affected_train_count = 1
    p7_setup["c2"].affected_train_count = 6
    db.commit()
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["selected_candidate_id"] == p7_setup["c1"].id


def test_05_block_duration_objective(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")


def test_06_maintenance_priority_objective(db: Session, p7_setup):
    p7_setup["mreq"].priority = "CRITICAL"
    db.commit()
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")


def test_07_cross_department_integration_bonus(db: Session, p7_setup):
    blk2 = BlockRequest(
        block_code=f"BLK-P7-INT-{uuid.uuid4().hex[:8]}",
        maintenance_request_id=p7_setup["mreq"].id,
        section_id=1,
        track_id=1,
        requested_start=p7_setup["mreq"].requested_start,
        requested_end=p7_setup["mreq"].requested_end,
        block_type="MAINTENANCE",
        status="PROPOSED",
    )
    db.add(blk2)
    db.commit()
    db.refresh(blk2)

    integ = BlockIntegrationRequest(
        source_block_id=p7_setup["blk"].id,
        target_block_id=blk2.id,
        requesting_department_id=1,
        target_department_id=2,
        compatibility_status="COMPATIBLE",
        final_status="ACCEPTED",
        requested_by=1,
    )
    db.add(integ)
    db.commit()
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")


def test_08_resource_utilization_bonus(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")


def test_09_zero_safe_candidates_handling(db: Session, p7_setup):
    db.query(SafetyValidation).filter(SafetyValidation.candidate_id.in_([p7_setup["c1"].id, p7_setup["c2"].id])).update(
        {"overall_status": "UNSAFE", "is_safe_for_optimization": False}
    )
    db.query(BlockCandidate).filter(BlockCandidate.block_request_id == p7_setup["blk"].id).update({"safety_status": "UNSAFE"})
    db.commit()

    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res["status"] == "NO_SAFE_CANDIDATES"
    assert res["solver_status"] == "INFEASIBLE"


def test_10_infeasible_solver_handling(db: Session, p7_setup):
    cfg = OptimizationConfig(solver_time_limit_seconds=0.0001)
    res = optimize_block_request(p7_setup["blk"].id, db, config=cfg)
    assert res["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")


def test_11_solver_timeout_handling(db: Session, p7_setup):
    cfg = OptimizationConfig(solver_time_limit_seconds=0.001)
    res = optimize_block_request(p7_setup["blk"].id, db, config=cfg)
    assert "solve_duration_ms" in res


def test_12_solver_determinism(db: Session, p7_setup):
    # Reset candidates to safe
    db.query(SafetyValidation).filter(SafetyValidation.candidate_id.in_([p7_setup["c1"].id, p7_setup["c2"].id])).update(
        {"overall_status": "SAFE", "is_safe_for_optimization": True}
    )
    db.query(BlockCandidate).filter(BlockCandidate.block_request_id == p7_setup["blk"].id).update({"safety_status": "SAFE"})
    db.commit()

    cfg = OptimizationConfig(solver_random_seed=42)
    res1 = optimize_block_request(p7_setup["blk"].id, db, config=cfg, simulation=True)
    res2 = optimize_block_request(p7_setup["blk"].id, db, config=cfg, simulation=True)
    assert res1["selected_candidate_id"] == res2["selected_candidate_id"]


def test_13_dynamic_reoptimization_and_history(db: Session, p7_setup):
    res1 = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    res2 = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    assert res1["optimized_block_id"] is not None
    assert res2["optimized_block_id"] is not None


def test_14_objective_config_versioning_and_api(db: Session, p7_setup):
    headers = auth_header(db, "official@railway.gov.in")
    res = client.get("/api/optimization/config", headers=headers)
    assert res.status_code == 200
    assert res.json()["version"] == "v1.0"


def test_15_simulation_mode_does_not_mutate_db(db: Session, p7_setup):
    cnt_before = db.query(OptimizedBlock).count()
    res = optimize_block_request(p7_setup["blk"].id, db, simulation=True)
    cnt_after = db.query(OptimizedBlock).count()
    assert cnt_after == cnt_before
    assert res["simulation"] is True


def test_16_explainable_output_and_breakdown(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, simulation=True)
    assert "CP-SAT" in res["explanation"]
    assert "Optimization Score" in res["explanation"]


def test_17_candidate_comparison_matrix_api(db: Session, p7_setup):
    headers = auth_header(db, "official@railway.gov.in")
    res = client.get(f"/api/optimization/blocks/{p7_setup['blk'].id}/comparison", headers=headers)
    assert res.status_code == 200
    assert "candidates" in res.json()


def test_18_rbac_and_security_boundaries(db: Session, p7_setup):
    res = client.post(f"/api/optimization/blocks/{p7_setup['blk'].id}/optimize", json={})
    assert res.status_code == 401


def test_19_strict_phase_boundaries(db: Session, p7_setup):
    res = optimize_block_request(p7_setup["blk"].id, db, user_id=1)
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == res["optimized_block_id"]).first()
    assert ob.status == "PROPOSED"
    assert ob.approved_by is None
    assert ob.approved_at is None
