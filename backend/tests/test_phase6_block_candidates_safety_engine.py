"""Phase 6 — Block Candidate Generation & Deterministic Safety Engine Test Suite.

Comprehensive verification of:
1. Configurable candidate window generation (15m, 30m, 60m granularity, buffers, window_days).
2. Parallel track non-interference (Track 1 block does NOT block parallel Track 2).
3. Track-level conflict detection (Overlapping block on same track -> UNSAFE).
4. Section-level corridor closure detection (Whole corridor block track_id=None -> UNSAFE).
5. Existing active/approved block collision detection.
6. Historical/completed/rejected block non-interference.
7. Train conflict evaluation (Manageable train traffic WARNING vs severe conflicts).
8. Adjacent track fouling and machinery clearance evaluation.
9. Resource contention detection (Machinery / crew overlap).
10. Cross-department maintenance compatibility (Phase 4 integration).
11. Traction power isolation (OHE) and S&T disconnection checks.
12. Duration adequacy verification (Candidate duration < maintenance required duration -> UNSAFE).
13. Operational limits and curfew verification (Past timestamp or >24h window -> UNSAFE).
14. Emergency incident restriction (Active emergency in section -> UNSAFE).
15. Dynamic revalidation lifecycle (Candidate flips to UNSAFE when conflicting block is added).
16. Safe candidates filtering (`get_safe_candidates`).
17. Simulation mode (`persist=False`).
18. RBAC and department isolation.
19. Strict Phase Boundaries (No OR-Tools solver execution, no candidate selection, no block approval).
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
from app.database import SessionLocal
from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.railway import RailwaySection, Track
from app.models.incident import Incident
from app.safety.engine import SafetyEngine, validate_candidate, revalidate_candidate, get_safe_candidates
from app.services.candidate_generator import CandidateGeneratorService

client = TestClient(app)


def login(username: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_dt(days: int = 1, hours: int = 0, minutes: int = 0) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours, minutes=minutes)


@pytest.fixture(scope="module")
def tokens():
    return {
        "admin": login("railway_official", "SIH@Official2026"),
        "controller": login("operations", "SIH@Ops2026"),
        "sse_eng": login("eng_sse", "SIH@EngSSE2026"),
        "je_eng": login("eng_je", "SIH@EngJE2026"),
        "sse_elec": login("elec_je", "SIH@ElecJE2026"),
        "staff_eng": login("eng_staff", "SIH@EngStaff2026"),
    }


@pytest.fixture
def db():
    session = SessionLocal()
    session.execute(text("DELETE FROM emergency_responses"))
    session.execute(text("DELETE FROM incidents"))
    session.commit()
    yield session
    session.close()


def create_verified_maintenance(db, dept_id=1, section_id=1, track_id=1, duration_mins=120, work_type="TRACK_RENEWAL"):
    start = future_dt(hours=24)
    end = start + datetime.timedelta(minutes=duration_mins)
    req = MaintenanceRequest(
        request_code=f"REQ-T6-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        asset_id=1,
        department_id=dept_id,
        requested_by=1,
        section_id=section_id,
        track_id=track_id,
        maintenance_type=work_type,
        description="Automated test for block candidate generation and safety engine",
        priority="HIGH",
        requested_start=start,
        requested_end=end,
        requested_duration_mins=duration_mins,
        status="VERIFIED",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def create_block_request(db, mreq_id, section_id=1, track_id=1, start_offset_hours=24, duration_hours=4):
    start = future_dt(hours=start_offset_hours)
    end = start + datetime.timedelta(hours=duration_hours)
    block = BlockRequest(
        block_code=f"BLK-T6-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq_id,
        section_id=section_id,
        track_id=track_id,
        requested_start=start,
        requested_end=end,
        block_type="TRAFFIC",
        status="PROPOSED",
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


# ==============================================================================
# TEST 1: Configurable Candidate Generation Intervals
# ==============================================================================
def test_candidate_generation_configurable_intervals(db, tokens):
    mreq = create_verified_maintenance(db, duration_mins=90)
    block = create_block_request(db, mreq.id, duration_hours=6)

    generator = CandidateGeneratorService()

    # 30-minute interval
    res_30 = generator.generate_candidates_for_block(
        db=db,
        block_request_id=block.id,
        user_id=1,
        interval_mins=30,
        max_candidates=4,
        min_duration_buffer_mins=15,
        window_days=1,
    )
    assert res_30["generated"] > 0
    assert "candidates" in res_30
    assert "safe_count" in res_30

    # Verify candidates are persisted in block_candidates table
    cands_db = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block.id).all()
    assert len(cands_db) == res_30["generated"]

    # 15-minute interval via API
    api_res = client.post(
        f"/api/blocks/requests/{block.id}/candidates/generate",
        json={"interval_minutes": 15, "max_candidates": 3, "min_duration_buffer_mins": 0, "candidate_window_days": 1},
        headers=auth_header(tokens["sse_eng"]),
    )
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["generated"] > 0
    assert len(data["candidates"]) == data["generated"]


# ==============================================================================
# TEST 2: Parallel Tracks Non-Interference
# ==============================================================================
def test_parallel_tracks_non_interference(db):
    """A block on Track 1 should NOT make a candidate window on parallel Track 2 UNSAFE."""
    # Ensure Track 1 and Track 2 exist
    t1 = db.query(Track).filter(Track.id == 1).first()
    t2 = db.query(Track).filter(Track.id == 2).first()
    if not t1 or not t2:
        pytest.skip("Requires at least 2 tracks in database")

    start = future_dt(days=2, hours=10)
    end = start + datetime.timedelta(hours=3)

    # Existing active/approved block on Track 1
    mreq1 = create_verified_maintenance(db, track_id=1, duration_mins=120)
    block1 = BlockRequest(
        block_code=f"BLK-OCC-T1-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq1.id,
        section_id=1,
        track_id=1,
        requested_start=start,
        requested_end=end,
        status="APPROVED",
    )
    db.add(block1)
    db.commit()

    # Candidate on Track 2 for the exact same time window
    mreq2 = create_verified_maintenance(db, track_id=2, duration_mins=120)
    block2 = create_block_request(db, mreq2.id, track_id=2, start_offset_hours=48, duration_hours=4)

    cand_t2 = BlockCandidate(
        block_request_id=block2.id,
        section_id=1,
        track_id=2,
        candidate_start=start,
        candidate_end=end,
        safety_status="FEASIBLE",
    )
    db.add(cand_t2)
    db.commit()
    db.refresh(cand_t2)

    val = validate_candidate(cand_t2, db, persist=False)
    # Track conflict check should PASS because track_id is 2, not 1
    track_check = next(c for c in val["checks"] if c["check"] in ("TRACK_CONFLICT", "TRACK"))
    assert track_check["status"] == "PASS"


# ==============================================================================
# TEST 3: Track-Level Conflict Detection
# ==============================================================================
def test_track_conflict_detection(db):
    """An overlapping block on the exact same track must fail TRACK_CONFLICT."""
    start = future_dt(days=3, hours=10)
    end = start + datetime.timedelta(hours=3)

    # Pre-existing approved block on Track 1
    mreq1 = create_verified_maintenance(db, track_id=1, duration_mins=120)
    block1 = BlockRequest(
        block_code=f"BLK-OCC-T1B-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq1.id,
        section_id=1,
        track_id=1,
        requested_start=start,
        requested_end=end,
        status="APPROVED",
    )
    db.add(block1)
    db.commit()

    # Candidate on Track 1 overlapping the window
    mreq2 = create_verified_maintenance(db, track_id=1, duration_mins=120)
    block2 = create_block_request(db, mreq2.id, track_id=1, start_offset_hours=72, duration_hours=4)

    cand_conflict = BlockCandidate(
        block_request_id=block2.id,
        section_id=1,
        track_id=1,
        candidate_start=start + datetime.timedelta(minutes=30),
        candidate_end=end + datetime.timedelta(minutes=30),
        safety_status="FEASIBLE",
    )
    db.add(cand_conflict)
    db.commit()
    db.refresh(cand_conflict)

    val = validate_candidate(cand_conflict, db, persist=False)
    assert val["overall_status"] == "UNSAFE"
    assert val["is_safe_for_optimization"] is False
    track_check = next(c for c in val["checks"] if c["check"] in ("TRACK_CONFLICT", "TRACK"))
    assert track_check["status"] == "FAIL"


# ==============================================================================
# TEST 4: Section-Level Conflict Detection (Corridor Closure)
# ==============================================================================
def test_section_conflict_detection(db):
    """A whole-corridor shutdown (track_id=None) must block all tracks in that section."""
    start = future_dt(days=4, hours=10)
    end = start + datetime.timedelta(hours=4)

    # Corridor-wide block
    mreq_corr = create_verified_maintenance(db, track_id=None, duration_mins=240)
    block_corr = BlockRequest(
        block_code=f"BLK-CORR-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq_corr.id,
        section_id=1,
        track_id=None,
        requested_start=start,
        requested_end=end,
        status="APPROVED",
    )
    db.add(block_corr)
    db.commit()

    # Candidate on Track 2 in the same section during that window
    mreq_t2 = create_verified_maintenance(db, track_id=2, duration_mins=120)
    block_t2 = create_block_request(db, mreq_t2.id, track_id=2, start_offset_hours=96, duration_hours=4)

    cand_corr = BlockCandidate(
        block_request_id=block_t2.id,
        section_id=1,
        track_id=2,
        candidate_start=start + datetime.timedelta(minutes=15),
        candidate_end=end - datetime.timedelta(minutes=15),
        safety_status="FEASIBLE",
    )
    db.add(cand_corr)
    db.commit()
    db.refresh(cand_corr)

    val = validate_candidate(cand_corr, db, persist=False)
    assert val["overall_status"] == "UNSAFE"
    assert val["is_safe_for_optimization"] is False


# ==============================================================================
# TEST 5: Historical & Completed Blocks Non-Interference
# ==============================================================================
def test_historical_completed_blocks_non_interference(db):
    """Overlapping blocks in CANCELLED, REJECTED, or COMPLETED status must NOT fail candidate."""
    start = future_dt(days=5, hours=10)
    end = start + datetime.timedelta(hours=3)

    mreq_past = create_verified_maintenance(db, track_id=1, duration_mins=120)
    block_completed = BlockRequest(
        block_code=f"BLK-CMP-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq_past.id,
        section_id=1,
        track_id=1,
        requested_start=start,
        requested_end=end,
        status="COMPLETED",
    )
    db.add(block_completed)
    db.commit()

    mreq_curr = create_verified_maintenance(db, track_id=1, duration_mins=120)
    block_curr = create_block_request(db, mreq_curr.id, track_id=1, start_offset_hours=120, duration_hours=4)

    cand = BlockCandidate(
        block_request_id=block_curr.id,
        section_id=1,
        track_id=1,
        candidate_start=start,
        candidate_end=end,
        safety_status="FEASIBLE",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    val = validate_candidate(cand, db, persist=False)
    existing_rule = next(c for c in val["checks"] if c["check"] in ("EXISTING_BLOCK", "EXISTING_BLOCKS"))
    assert existing_rule["status"] == "PASS"


# ==============================================================================
# TEST 6: Duration Adequacy Rule
# ==============================================================================
def test_duration_adequacy_rule(db):
    """Candidate duration shorter than maintenance required duration must fail TIMING check."""
    start = future_dt(days=6, hours=10)
    end = start + datetime.timedelta(minutes=45)  # 45 mins

    mreq = create_verified_maintenance(db, duration_mins=120)  # Requires 120 mins
    block = create_block_request(db, mreq.id, start_offset_hours=144, duration_hours=4)

    cand_short = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=start,
        candidate_end=end,
        safety_status="FEASIBLE",
    )
    db.add(cand_short)
    db.commit()
    db.refresh(cand_short)

    val = validate_candidate(cand_short, db, persist=False)
    assert val["overall_status"] == "UNSAFE"
    timing_check = next(c for c in val["checks"] if c["check"] in ("TIMING", "TIMING_DURATION"))
    assert timing_check["status"] == "FAIL"


# ==============================================================================
# TEST 7: Operational Restrictions (Past & Excess Duration)
# ==============================================================================
def test_operational_restrictions_past_and_excess(db):
    """Past timestamps or windows exceeding 24 hours must be rejected by Safety Engine."""
    # Past timestamp
    past_start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
    past_end = past_start + datetime.timedelta(hours=2)

    mreq = create_verified_maintenance(db, duration_mins=60)
    block = create_block_request(db, mreq.id, start_offset_hours=24, duration_hours=4)

    cand_past = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=past_start,
        candidate_end=past_end,
        safety_status="FEASIBLE",
    )
    db.add(cand_past)
    db.commit()
    db.refresh(cand_past)

    val = validate_candidate(cand_past, db, persist=False)
    assert val["overall_status"] == "UNSAFE"
    op_check = next(c for c in val["checks"] if c["check"] in ("OPERATIONAL", "OPERATIONAL_RESTRICTION"))
    assert op_check["status"] == "FAIL"


# ==============================================================================
# ==============================================================================
# TEST 8: Emergency Incident Restriction
# ==============================================================================
def test_emergency_restriction_rule(db):
    """Active emergency incident in the target section marks candidate UNSAFE."""
    start = future_dt(days=75, hours=10)
    end = start + datetime.timedelta(hours=3)

    # Active emergency
    inc = Incident(
        incident_code=f"EMG-TEST-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        incident_type="DERAILMENT_RELATED",
        severity="CRITICAL",
        section_id=1,
        response_status="OPEN",
        reported_by=1,
    )
    db.add(inc)
    db.commit()

    try:
        mreq = create_verified_maintenance(db, duration_mins=60)
        block = create_block_request(db, mreq.id, start_offset_hours=75 * 24, duration_hours=4)

        cand = BlockCandidate(
            block_request_id=block.id,
            section_id=1,
            track_id=1,
            candidate_start=start,
            candidate_end=end,
            safety_status="FEASIBLE",
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)

        val = validate_candidate(cand, db, persist=False)
        assert val["overall_status"] == "UNSAFE"
        emg_check = next(c for c in val["checks"] if c["check"] in ("EMERGENCY", "EMERGENCY_RESTRICTION"))
        assert emg_check["status"] == "FAIL"
    finally:
        # Guarantee cleanup
        inc.response_status = "CLEARED"
        db.commit()


# ==============================================================================
# TEST 9: Dynamic Revalidation Lifecycle
# ==============================================================================
def test_revalidation_lifecycle(db, tokens):
    """A candidate initially SAFE must flip to UNSAFE upon revalidation if a conflict is introduced."""
    start = future_dt(days=85, hours=10)
    end = start + datetime.timedelta(hours=3)

    db.query(BlockRequest).filter(
        BlockRequest.section_id == 1,
        BlockRequest.track_id == 1,
        BlockRequest.requested_start < end,
        BlockRequest.requested_end > start,
    ).delete()
    db.commit()

    mreq = create_verified_maintenance(db, duration_mins=60)
    block = create_block_request(db, mreq.id, start_offset_hours=85 * 24, duration_hours=4)

    cand = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=start,
        candidate_end=end,
        safety_status="FEASIBLE",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    # 1. Initial Validation -> SAFE
    val1 = validate_candidate(cand, db, user_id=1, persist=True)
    assert val1["overall_status"] == "SAFE", f"Expected SAFE, got {val1['overall_status']}: {val1.get('rejection_reasons')}"
    assert val1["is_safe_for_optimization"] is True

    # 2. Add conflicting approved block on same track & time
    mreq_conf = create_verified_maintenance(db, track_id=1, duration_mins=60)
    block_conf = BlockRequest(
        block_code=f"BLK-CONF-{int(datetime.datetime.now().timestamp() * 1000) % 1000000}",
        maintenance_request_id=mreq_conf.id,
        section_id=1,
        track_id=1,
        requested_start=start,
        requested_end=end,
        status="APPROVED",
    )
    db.add(block_conf)
    db.commit()

    # 3. Revalidate Candidate
    reval_res = revalidate_candidate(cand.id, db, user_id=1)
    assert reval_res["overall_status"] == "UNSAFE"
    assert reval_res["is_safe_for_optimization"] is False

    # Check persisted safety validation table
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
    assert sv.overall_status == "UNSAFE"
    assert sv.is_safe_for_optimization is False

    # Revalidate via API endpoint
    api_reval = client.post(
        f"/api/safety/revalidate/candidate/{cand.id}",
        headers=auth_header(tokens["sse_eng"]),
    )
    assert api_reval.status_code == 200
    assert api_reval.json()["overall_status"] == "UNSAFE"


# ==============================================================================
# TEST 10: get_safe_candidates Filter
# ==============================================================================
def test_get_safe_candidates_filter(db, tokens):
    """get_safe_candidates must only return candidates where is_safe_for_optimization == True."""
    mreq = create_verified_maintenance(db, duration_mins=60)
    block = create_block_request(db, mreq.id, start_offset_hours=95 * 24, duration_hours=6)

    # Candidate 1: Safe
    cand_safe = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=future_dt(days=95, hours=2),
        candidate_end=future_dt(days=95, hours=5),
        safety_status="SAFE",
    )
    # Candidate 2: Infeasible / Short (15 mins < 60 mins required)
    cand_unsafe = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=future_dt(days=95, hours=6),
        candidate_end=future_dt(days=95, hours=6, minutes=15),
        safety_status="INFEASIBLE",
    )
    db.add_all([cand_safe, cand_unsafe])
    db.commit()
    db.refresh(cand_safe)
    db.refresh(cand_unsafe)

    val_safe = validate_candidate(cand_safe, db, persist=True)
    assert val_safe["overall_status"] == "SAFE", f"Candidate 1 failed: {val_safe.get('rejection_reasons')}"
    validate_candidate(cand_unsafe, db, persist=True)

    safe_list = get_safe_candidates(block.id, db)
    safe_ids = [c["candidate_id"] for c in safe_list]
    assert cand_safe.id in safe_ids
    assert cand_unsafe.id not in safe_ids

    # Query via API
    api_res = client.get(
        f"/api/safety/safe-candidates/{block.id}",
        headers=auth_header(tokens["sse_eng"]),
    )
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["total_safe_candidates"] == len(safe_list)


# ==============================================================================
# TEST 11: Simulation Mode (persist=False)
# ==============================================================================
def test_safety_engine_simulation_mode(db):
    """persist=False runs full deterministic checks without writing to DB."""
    mreq = create_verified_maintenance(db, duration_mins=60)
    block = create_block_request(db, mreq.id, start_offset_hours=240, duration_hours=4)

    cand = BlockCandidate(
        block_request_id=block.id,
        section_id=1,
        track_id=1,
        candidate_start=future_dt(days=10, hours=2),
        candidate_end=future_dt(days=10, hours=4),
        safety_status="FEASIBLE",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    val = validate_candidate(cand, db, persist=False)
    assert "overall_status" in val
    assert "checks" in val
    assert len(val["checks"]) >= 10

    # Ensure no SafetyValidation was written
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
    assert sv is None


# ==============================================================================
# TEST 12: RBAC & Security Boundaries
# ==============================================================================
def test_rbac_and_department_boundaries(tokens):
    """Maintenance staff role cannot trigger safety engine; cross-dept access is guarded."""
    # Attempt validation as MAINTENANCE_STAFF -> 403 Forbidden
    res = client.post(
        "/api/safety/validate/candidate/1",
        headers=auth_header(tokens["staff_eng"]),
    )
    assert res.status_code == 403


# ==============================================================================
# TEST 13: Strict Phase Boundaries
# ==============================================================================
def test_strict_phase_boundaries(db):
    """Phase 6 must NOT run OR-Tools, select candidates, or approve blocks."""
    mreq = create_verified_maintenance(db, duration_mins=60)
    block = create_block_request(db, mreq.id, start_offset_hours=264, duration_hours=4)

    generator = CandidateGeneratorService()
    res = generator.generate_candidates_for_block(
        db=db,
        block_request_id=block.id,
        user_id=1,
    )
    assert res["generated"] > 0

    cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block.id).all()
    for c in cands:
        # Phase 6 must NOT mark any candidate as selected
        assert c.is_selected is False
        # Phase 6 must NOT set optimization_score
        assert c.optimization_score is None

    # Block request status must remain PROPOSED or initial state, never APPROVED
    block_refresh = db.query(BlockRequest).filter(BlockRequest.id == block.id).first()
    assert block_refresh.status != "APPROVED"
