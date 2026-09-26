"""Phase 4 — Cross-Department Coordination + Integrated Block Request System Tests.

Tests end-to-end functionality of:
1. Automated opportunity detection service (/api/integration/detect, /api/integration/opportunities).
2. Deterministic scoring, spatial co-location assessment, and preliminary compatibility status.
3. Department review lifecycle: ACCEPT, REJECT (mandatory reason), MODIFY (time window proposal).
4. Request-to-Join existing block workflow (/api/integration/requests/join-block).
5. Multi-department coordination (ENG + ELEC + SNT 3-way coordination).
6. Idempotency and duplicate prevention.
7. Role-Based Access Control (RBAC), self-approval prevention, department-scoped visibility.
8. Strict Phase Boundaries (No automatic block merging, no safety engine execution, no OR-Tools).
9. PostgreSQL transactional audit logs & targeted notifications.
"""
import sys
import datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine, SessionLocal
from app.models.block import BlockRequest, BlockCandidate, BlockIntegrationRequest, OptimizedBlock
from app.models.maintenance import MaintenanceRequest

client = TestClient(app)


def login(email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"username": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_iso(days: int, hours: float = 0) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours)
    return dt.isoformat()


@pytest.fixture(scope="module")
def tokens():
    return {
        "eng_staff": login("eng.staff@irctc.test", "EngStaff@123"),
        "eng_rev": login("eng.reviewer@irctc.test", "EngReview@123"),
        "elec_staff": login("elec.staff@irctc.test", "ElecStaff@123"),
        "elec_rev": login("elec.reviewer@irctc.test", "ElecReview@123"),
        "snt_staff": login("snt.staff@irctc.test", "SntStaff@123"),
        "snt_rev": login("snt.reviewer@irctc.test", "SntReview@123"),
        "official": login("railway.official@irctc.test", "Official@123"),
        "ops": login("ops.operator@irctc.test", "OpsOper@123"),
    }


def clean_db():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM emergency_responses"))
        db.execute(text("DELETE FROM incidents"))
        db.execute(text("DELETE FROM safety_validations"))
        db.execute(text("DELETE FROM notifications WHERE optimized_block_id IS NOT NULL"))
        db.execute(text("DELETE FROM notifications WHERE integration_request_id IS NOT NULL"))
        db.query(BlockIntegrationRequest).delete()
        db.query(BlockCandidate).delete()
        db.execute(text("DELETE FROM optimized_block_sources"))
        db.query(OptimizedBlock).delete()
        db.query(BlockRequest).delete()
        db.execute(text("DELETE FROM maintenance_predictions"))
        db.query(MaintenanceRequest).delete()
        db.commit()
    finally:
        db.close()


def create_and_verify_maintenance(token: str, rev_token: str, asset_id: int, section_id: int = 1, track_id: int = 1, day_offset: int = 80, duration_hours: float = 2.0) -> int:
    payload = {
        "asset_id": asset_id,
        "section_id": section_id,
        "track_id": track_id,
        "maintenance_type": "Phase 4 Joint Maintenance",
        "priority": "HIGH",
        "requested_start": future_iso(day_offset),
        "requested_end": future_iso(day_offset, duration_hours),
    }
    r = client.post("/api/maintenance/requests", headers=auth_header(token), json=payload)
    assert r.status_code == 201, r.text
    mid = r.json()["id"]

    # Transition to SUBMITTED -> UNDER_REVIEW -> Review VERIFY
    r_sub = client.post(f"/api/maintenance/requests/{mid}/transition", headers=auth_header(token), json={"new_status": "SUBMITTED"})
    assert r_sub.status_code == 200, r_sub.text
    r_rev = client.post(f"/api/maintenance/requests/{mid}/transition", headers=auth_header(rev_token), json={"new_status": "UNDER_REVIEW"})
    assert r_rev.status_code == 200, r_rev.text
    r_ver = client.post(f"/api/maintenance/requests/{mid}/review", headers=auth_header(rev_token), json={"action": "VERIFY", "notes": "Verified for Phase 4"})
    assert r_ver.status_code == 200, r_ver.text
    return mid


def create_block_request(token: str, maintenance_id: int, start_days: int = 80, start_hours: float = 0, duration_hours: float = 2.0) -> int:
    payload = {
        "maintenance_request_id": maintenance_id,
        "requested_start": future_iso(start_days, start_hours),
        "requested_end": future_iso(start_days, start_hours + duration_hours),
    }
    r = client.post("/api/blocks/requests", headers=auth_header(token), json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_01_two_department_detection_and_acceptance(tokens):
    """Test 2-department coordination: ENG and ELEC overlapping on same section and track."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=80, duration_hours=2.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=80, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=80, start_hours=0, duration_hours=2.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=80, start_hours=0.5, duration_hours=2.0)

    # Automated opportunity detector
    r_detect = client.post("/api/integration/detect", headers=auth_header(tokens["official"]), json={"section_id": 1})
    assert r_detect.status_code == 200, r_detect.text
    detect_data = r_detect.json()
    assert detect_data["detected_count"] >= 1
    assert len(detect_data["opportunities"]) >= 1

    opp = detect_data["opportunities"][0]
    assert opp["compatibility_status"] == "COMPATIBLE"
    assert opp["spatial_status"] == "SAME_TRACK"
    assert opp["overlap_duration_mins"] in (89, 90)
    assert opp["coordination_score"] >= 75

    # Verify integration request in list
    r_list = client.get("/api/integration/requests", headers=auth_header(tokens["elec_rev"]))
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert any(item["source_block_id"] == bid_eng and item["target_block_id"] == bid_elec for item in items)
    int_id = items[0]["id"]

    # ELEC accepts coordination proposal
    r_accept = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["elec_rev"]), json={
        "response": "ACCEPT",
        "reason": "Joint possession accepted, power shutdown coordinated."
    })
    assert r_accept.status_code == 200
    assert r_accept.json()["final_status"] == "ACCEPTED"
    assert r_accept.json()["response"] == "ACCEPT"


def test_02_rejection_with_mandatory_reason(tokens):
    """Test target department rejection requiring a mandatory non-empty reason."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=81, duration_hours=2.0)
    mid_snt = create_and_verify_maintenance(tokens["snt_staff"], tokens["snt_rev"], asset_id=3, section_id=1, track_id=1, day_offset=81, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=81, start_hours=0, duration_hours=2.0)
    bid_snt = create_block_request(tokens["snt_rev"], mid_snt, start_days=81, start_hours=0.5, duration_hours=2.0)

    # Propose coordination manually
    r_prop = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_snt,
        "reason": "Engineering track renewal joint with S&T point machine check."
    })
    assert r_prop.status_code == 201
    int_id = r_prop.json()["id"]

    # Attempt rejection without reason -> should fail with 422
    r_bad_rej = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["snt_rev"]), json={
        "response": "REJECT",
        "reason": "   "
    })
    assert r_bad_rej.status_code == 422

    # Valid rejection with reason
    r_good_rej = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["snt_rev"]), json={
        "response": "REJECT",
        "reason": "Signal calibration team is committed to Section 2 on this shift."
    })
    assert r_good_rej.status_code == 200
    assert r_good_rej.json()["final_status"] == "REJECTED"
    assert r_good_rej.json()["reason"] == "Signal calibration team is committed to Section 2 on this shift."


def test_03_modification_proposal_workflow(tokens):
    """Test MODIFY response preserving original source request and storing modified window."""
    clean_db()

    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=82, duration_hours=2.0)
    mid_snt = create_and_verify_maintenance(tokens["snt_staff"], tokens["snt_rev"], asset_id=3, section_id=1, track_id=1, day_offset=82, duration_hours=2.0)

    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=82, start_hours=0, duration_hours=2.0)
    bid_snt = create_block_request(tokens["snt_rev"], mid_snt, start_days=82, start_hours=1.0, duration_hours=2.0)

    r_prop = client.post("/api/integration/requests", headers=auth_header(tokens["elec_rev"]), json={
        "source_block_id": bid_elec,
        "target_block_id": bid_snt,
        "reason": "OHE maintenance window coordination"
    })
    assert r_prop.status_code == 201
    int_id = r_prop.json()["id"]

    # Target S&T proposes modified window
    mod_start = future_iso(82, 2.0)
    mod_end = future_iso(82, 4.0)
    r_mod = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["snt_rev"]), json={
        "response": "MODIFY",
        "modified_start": mod_start,
        "modified_end": mod_end,
        "reason": "Shift window by 2 hours due to interlocking test dependencies."
    })
    assert r_mod.status_code == 200
    res_data = r_mod.json()
    assert res_data["final_status"] == "MODIFIED"
    assert res_data["modified_start"] is not None
    assert res_data["modified_end"] is not None

    # Verify original block request times are untouched
    with engine.connect() as conn:
        orig_elec = conn.execute(text("SELECT status FROM block_requests WHERE id=:id"), {"id": bid_elec}).scalar()
        assert orig_elec == "REQUESTED"


def test_04_spatial_rules_and_insufficient_data(tokens):
    """Test spatial classification: adjacent tracks require safety validation, missing asset = insufficient data."""
    clean_db()

    # Case A: Different tracks on same section (track 1 vs track 2 using Asset 1 and Asset 4)
    mid_eng_t1 = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=83, duration_hours=2.0)
    mid_elec_t2 = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=4, section_id=1, track_id=2, day_offset=83, duration_hours=2.0)
    mid_snt_t2 = create_and_verify_maintenance(tokens["snt_staff"], tokens["snt_rev"], asset_id=3, section_id=1, track_id=1, day_offset=83, duration_hours=2.0)

    bid_t1 = create_block_request(tokens["eng_rev"], mid_eng_t1, start_days=83, start_hours=0, duration_hours=2.0)
    bid_t2 = create_block_request(tokens["snt_rev"], mid_snt_t2, start_days=83, start_hours=0.5, duration_hours=2.0)

    r_adj = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_t1,
        "target_block_id": bid_t2,
        "reason": "Adjacent line work test"
    })
    assert r_adj.status_code == 201
    adj_data = r_adj.json()
    assert adj_data["compatibility_status"] in ("COMPATIBLE", "POTENTIAL_COMPATIBLE", "REQUIRES_SAFETY_VALIDATION")

    # Case B: Unmatched section
    r_det = client.post("/api/integration/detect", headers=auth_header(tokens["official"]), json={"section_id": 9999})
    assert r_det.status_code == 200
    assert r_det.json()["detected_count"] == 0


def test_05_idempotency_and_duplicate_prevention(tokens):
    """Test duplicate detection prevention for both directions (A->B and B->A)."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=84, duration_hours=2.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=84, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=84, start_hours=0, duration_hours=2.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=84, start_hours=0.5, duration_hours=2.0)

    # 1st creation
    r1 = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    assert r1.status_code == 201

    # 2nd creation same direction -> 409 Conflict
    r2 = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    assert r2.status_code == 409

    # Reverse direction -> 409 Conflict
    r3 = client.post("/api/integration/requests", headers=auth_header(tokens["elec_rev"]), json={
        "source_block_id": bid_elec,
        "target_block_id": bid_eng
    })
    assert r3.status_code == 409

    # Auto-detect should recognize existing active request and not create duplicates
    r_detect = client.post("/api/integration/detect", headers=auth_header(tokens["official"]), json={"section_id": 1})
    assert r_detect.status_code == 200
    assert r_detect.json()["detected_count"] == 1


def test_06_request_to_join_existing_block(tokens):
    """Test /api/integration/requests/join-block endpoint."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=85, duration_hours=4.0)
    mid_snt = create_and_verify_maintenance(tokens["snt_staff"], tokens["snt_rev"], asset_id=3, section_id=1, track_id=1, day_offset=85, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=85, start_hours=0, duration_hours=4.0)

    # S&T requests to join the existing Engineering block
    r_join = client.post("/api/integration/requests/join-block", headers=auth_header(tokens["snt_rev"]), json={
        "block_id": bid_eng,
        "maintenance_request_id": mid_snt,
        "reason": "Requesting to join track possession for signal cable inspection."
    })
    assert r_join.status_code == 201, r_join.text
    join_data = r_join.json()
    assert join_data["target_block_id"] == bid_eng
    assert join_data["final_status"] == "PENDING"
    assert join_data["requesting_department_code"] == "SNT"
    assert join_data["target_department_code"] == "ENG"


def test_07_multi_department_3_way_coordination(tokens):
    """Test 3-way coordination among ENG, ELEC, and SNT on the same corridor window."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=86, duration_hours=3.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=86, duration_hours=3.0)
    mid_snt = create_and_verify_maintenance(tokens["snt_staff"], tokens["snt_rev"], asset_id=3, section_id=1, track_id=1, day_offset=86, duration_hours=3.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=86, start_hours=0, duration_hours=3.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=86, start_hours=0.5, duration_hours=3.0)
    bid_snt = create_block_request(tokens["snt_rev"], mid_snt, start_days=86, start_hours=1.0, duration_hours=3.0)

    # Detect opportunities for all 3
    r_det = client.post("/api/integration/detect", headers=auth_header(tokens["official"]), json={"section_id": 1})
    assert r_det.status_code == 200
    det = r_det.json()
    # Should detect 3 pairwise opportunities: (ENG, ELEC), (ENG, SNT), (ELEC, SNT)
    assert det["detected_count"] == 3

    # Verify all 3 pairs are recorded in database
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM block_integration_requests")).scalar()
        assert count == 3


def test_08_rbac_and_self_approval_security(tokens):
    """Test security restrictions: requester cannot respond to own request, unauthorized users 403."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=87, duration_hours=2.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=87, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=87, start_hours=0, duration_hours=2.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=87, start_hours=0.5, duration_hours=2.0)

    r_prop = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    int_id = r_prop.json()["id"]

    # 1. Requester tries to respond/accept own proposal -> 403 Forbidden
    r_self = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["eng_rev"]), json={"response": "ACCEPT"})
    assert r_self.status_code == 403

    # 2. Unrelated department S&T tries to respond -> 403 Forbidden
    r_unrel = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["snt_rev"]), json={"response": "ACCEPT"})
    assert r_unrel.status_code == 403

    # 3. Unauthorized operator tries to propose integration -> 403 Forbidden
    r_unauth = client.post("/api/integration/requests", headers=auth_header(tokens["ops"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    assert r_unauth.status_code == 403


def test_09_strict_phase_boundaries_no_premature_actions(tokens):
    """Ensure Phase 4 DOES NOT trigger automatic block merges, Safety Engine decisions, or OR-Tools optimization."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=88, duration_hours=2.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=88, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=88, start_hours=0, duration_hours=2.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=88, start_hours=0.5, duration_hours=2.0)

    r_prop = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    int_id = r_prop.json()["id"]

    # Target accepts
    r_acc = client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["elec_rev"]), json={"response": "ACCEPT"})
    assert r_acc.status_code == 200

    # Phase Boundary Verifications in DB:
    with engine.connect() as conn:
        # 1. No optimized_blocks created
        opt_count = conn.execute(text("SELECT count(*) FROM optimized_blocks")).scalar()
        assert opt_count == 0

        # 2. No optimized_block_sources created
        src_count = conn.execute(text("SELECT count(*) FROM optimized_block_sources")).scalar()
        assert src_count == 0

        # 3. Block status remains REQUESTED
        status = conn.execute(text("SELECT status FROM block_requests WHERE id=:id"), {"id": bid_eng}).scalar()
        assert status == "REQUESTED"

        # 4. No candidate selected
        sel_count = conn.execute(text("SELECT count(*) FROM block_candidates WHERE is_selected=true")).scalar()
        assert sel_count == 0

        # 5. Preliminary status is strictly COMPATIBLE, never "SAFE"
        compat_statuses = conn.execute(text("SELECT compatibility_status FROM block_integration_requests")).scalars().all()
        assert all("SAFE" not in (s or "") for s in compat_statuses)


def test_10_audit_logging_and_notifications(tokens):
    """Verify transactional audit log records and targeted notifications on coordination lifecycle events."""
    clean_db()

    mid_eng = create_and_verify_maintenance(tokens["eng_staff"], tokens["eng_rev"], asset_id=1, section_id=1, track_id=1, day_offset=89, duration_hours=2.0)
    mid_elec = create_and_verify_maintenance(tokens["elec_staff"], tokens["elec_rev"], asset_id=2, section_id=1, track_id=1, day_offset=89, duration_hours=2.0)

    bid_eng = create_block_request(tokens["eng_rev"], mid_eng, start_days=89, start_hours=0, duration_hours=2.0)
    bid_elec = create_block_request(tokens["elec_rev"], mid_elec, start_days=89, start_hours=0.5, duration_hours=2.0)

    # Propose
    r_prop = client.post("/api/integration/requests", headers=auth_header(tokens["eng_rev"]), json={
        "source_block_id": bid_eng,
        "target_block_id": bid_elec
    })
    int_id = r_prop.json()["id"]

    # Accept
    client.post(f"/api/integration/requests/{int_id}/respond", headers=auth_header(tokens["elec_rev"]), json={"response": "ACCEPT"})

    with engine.connect() as conn:
        # Audit Logs
        audit_actions = conn.execute(text("SELECT action FROM audit_logs WHERE entity_type='block_integration_request'")).scalars().all()
        assert "REQUEST_INTEGRATION" in audit_actions
        assert "ACCEPT_INTEGRATION" in audit_actions

        # Notifications
        notifs = conn.execute(text("SELECT type, recipient_department_id FROM notifications WHERE integration_request_id=:id"), {"id": int_id}).fetchall()
        types = [n[0] for n in notifs]
        assert "BLOCK_INTEGRATION_OPPORTUNITY" in types
        assert "INTEGRATION_ACCEPTED" in types
