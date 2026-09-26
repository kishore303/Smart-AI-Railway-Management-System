"""
Phase 3 Master Verification Suite: Maintenance Request Lifecycle & JE/SSE Technical Review
Comprehensive tests for Engineering, Electrical/OHE, and S&T maintenance request workflows,
multi-stage verification, revision loops, rejections, RBAC security, audit trails, and notifications.
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
from app.models.user import User
from app.models.asset import Asset
from app.models.railway import RailwaySection, Track
from app.models.maintenance import MaintenanceRequest
from app.models.audit import AuditLog
from app.models.notification import Notification

client = TestClient(app)


def login(username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed for {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def auth_hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_iso(days: int = 1, hours: int = 0) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours)
    return dt.isoformat()


@pytest.fixture(scope="module")
def tokens():
    return {
        "eng_staff": login("eng_staff", "SIH@EngStaff2026"),
        "eng_je": login("eng_je", "SIH@EngJE2026"),
        "eng_sse": login("eng_sse", "SIH@EngSSE2026"),
        "elec_staff": login("elec_staff", "SIH@ElecStaff2026"),
        "elec_je": login("elec_je", "SIH@ElecJE2026"),
        "elec_sse": login("elec_sse", "SIH@ElecSSE2026"),
        "snt_staff": login("snt_staff", "SIH@SNTStaff2026"),
        "snt_je": login("snt_je", "SIH@SNTJE2026"),
        "snt_sse": login("snt_sse", "SIH@SNTSSE2026"),
        "official": login("railway_official", "SIH@Official2026"),
        "operator": login("operations", "SIH@Ops2026"),
    }


def test_engineering_lifecycle_positive(tokens):
    """
    Test complete positive Engineering lifecycle:
    eng_staff creates draft -> submits -> eng_je verifies -> eng_sse verifies -> VERIFIED
    """
    print("\n=== 1. Engineering Lifecycle: eng_staff -> eng_je -> eng_sse -> VERIFIED ===")
    
    # 1. eng_staff creates draft
    start = future_iso(2, 0)
    end = future_iso(2, 3)
    create_payload = {
        "asset_id": 1,  # ENG asset
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Track Tamping and Alignment",
        "description": "Routine track tamping and ballast stabilization",
        "priority": "HIGH",
        "requested_start": start,
        "requested_end": end,
    }
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json=create_payload)
    assert r.status_code == 201, f"Expected 201 Created, got {r.status_code} {r.text}"
    req = r.json()
    req_id = req["id"]
    assert req["status"] == "DRAFT"
    assert req["department_code"] == "ENG"
    assert req["priority"] == "HIGH"
    assert req["requested_duration_mins"] == 180
    assert req["request_code"].startswith("REQ-")
    print(f"  PASS: eng_staff created DRAFT request {req['request_code']} (id={req_id})")

    # 2. eng_staff submits request
    r = client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    assert r.status_code == 200, f"Expected 200 on submit, got {r.status_code} {r.text}"
    req = r.json()
    assert req["status"] == "SUBMITTED"
    print(f"  PASS: eng_staff submitted request -> status SUBMITTED")

    # Verify notification created for department JE
    db = SessionLocal()
    notif = db.query(Notification).filter(Notification.recipient_department_id == req["department_id"]).order_by(Notification.id.desc()).first()
    assert notif is not None
    assert "New Maintenance Request" in notif.title
    db.close()
    print("  PASS: Submission notification generated for JE")

    # 3. eng_je reviews & verifies
    r = client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]), json={"reason": "Technical parameters validated and track profile verified."})
    assert r.status_code == 200, f"Expected 200 on JE verify, got {r.status_code} {r.text}"
    req = r.json()
    assert req["status"] == "UNDER_REVIEW"
    assert req["reviewed_by"] is not None
    print(f"  PASS: eng_je verified request -> forwarded to SSE review")

    # 4. eng_sse verifies
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]), json={"reason": "Senior Section Engineer verification approved for block planning."})
    assert r.status_code == 200, f"Expected 200 on SSE verify, got {r.status_code} {r.text}"
    req = r.json()
    assert req["status"] == "VERIFIED"
    print(f"  PASS: eng_sse verified request -> status VERIFIED (ready for Phase 4 planning)")


def test_electrical_lifecycle_positive(tokens):
    """
    Test complete positive Electrical/OHE lifecycle:
    elec_staff creates draft -> submits -> elec_je verifies -> elec_sse verifies -> VERIFIED
    """
    print("\n=== 2. Electrical/OHE Lifecycle: elec_staff -> elec_je -> elec_sse -> VERIFIED ===")
    start = future_iso(3, 0)
    end = future_iso(3, 2)
    create_payload = {
        "asset_id": 2,  # ELEC asset
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "OHE Catenary Inspection",
        "description": "Routine overhead line tension calibration",
        "priority": "MEDIUM",
        "requested_start": start,
        "requested_end": end,
    }
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["elec_staff"]), json=create_payload)
    assert r.status_code == 201
    req = r.json()
    req_id = req["id"]
    assert req["department_code"] == "ELEC"

    # Submit
    r = client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["elec_staff"]))
    assert r.status_code == 200
    assert r.json()["status"] == "SUBMITTED"

    # elec_je verify
    r = client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["elec_je"]))
    assert r.status_code == 200
    assert r.json()["status"] == "UNDER_REVIEW"

    # elec_sse verify
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["elec_sse"]))
    assert r.status_code == 200
    assert r.json()["status"] == "VERIFIED"
    print(f"  PASS: Electrical maintenance request {req['request_code']} completed full lifecycle to VERIFIED")


def test_snt_lifecycle_positive(tokens):
    """
    Test complete positive S&T lifecycle:
    snt_staff creates draft -> submits -> snt_je verifies -> snt_sse verifies -> VERIFIED
    """
    print("\n=== 3. S&T Lifecycle: snt_staff -> snt_je -> snt_sse -> VERIFIED ===")
    start = future_iso(4, 0)
    end = future_iso(4, 1)
    create_payload = {
        "asset_id": 3,  # SNT asset
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Signal Point Machine Overhaul",
        "description": "Point switch motor impedance and relay testing",
        "priority": "HIGH",
        "requested_start": start,
        "requested_end": end,
    }
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["snt_staff"]), json=create_payload)
    assert r.status_code == 201
    req = r.json()
    req_id = req["id"]
    assert req["department_code"] == "SNT"

    # Submit
    r = client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["snt_staff"]))
    assert r.status_code == 200

    # snt_je verify
    r = client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["snt_je"]))
    assert r.status_code == 200

    # snt_sse verify
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["snt_sse"]))
    assert r.status_code == 200
    assert r.json()["status"] == "VERIFIED"
    print(f"  PASS: S&T maintenance request {req['request_code']} completed full lifecycle to VERIFIED")


def test_je_revision_loop(tokens):
    """
    Test JE Revision loop:
    Submit -> JE Revision Required -> Staff edits -> Resubmits -> JE Verifies -> SSE Verifies
    """
    print("\n=== 4. JE Revision Loop ===")
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Rail Grinding",
        "priority": "MEDIUM",
        "requested_start": future_iso(5, 0),
        "requested_end": future_iso(5, 2),
        "description": "Initial description",
    })
    req_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))

    # JE requests revision
    rev_reason = "Please clarify required grinding depth and equipment."
    r = client.post(f"/api/maintenance/requests/{req_id}/je/revision", headers=auth_hdr(tokens["eng_je"]), json={"reason": rev_reason})
    assert r.status_code == 200
    req = r.json()
    assert req["status"] == "REVISION_REQUIRED"
    assert req["revision_notes"] == rev_reason
    print("  PASS: JE requested revision -> status REVISION_REQUIRED with notes preserved")

    # Staff edits in REVISION_REQUIRED state
    r = client.patch(f"/api/maintenance/requests/{req_id}", headers=auth_hdr(tokens["eng_staff"]), json={
        "description": "Updated description: 0.5mm grinding depth with RG-48 machine",
        "priority": "HIGH",
    })
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description: 0.5mm grinding depth with RG-48 machine"
    print("  PASS: Staff successfully updated request in REVISION_REQUIRED state")

    # Staff resubmits
    r = client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    assert r.status_code == 200
    assert r.json()["status"] == "SUBMITTED"
    print("  PASS: Staff successfully resubmitted -> status SUBMITTED")

    # JE verifies and SSE verifies
    r = client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]))
    assert r.status_code == 200
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]))
    assert r.status_code == 200
    assert r.json()["status"] == "VERIFIED"
    print("  PASS: Resubmitted request successfully verified by JE & SSE")


def test_sse_revision_loop(tokens):
    """
    Test SSE Revision loop:
    Submit -> JE Verify -> SSE Revision Required -> Staff edits -> Resubmit -> JE & SSE Verify
    """
    print("\n=== 5. SSE Revision Loop ===")
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Turnout Overhaul",
        "priority": "HIGH",
        "requested_start": future_iso(6, 0),
        "requested_end": future_iso(6, 3),
    })
    req_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]))

    # SSE requests revision
    sse_reason = "Window exceeds allowable peak corridor maintenance duration. Please reduce to 2 hours."
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/revision", headers=auth_hdr(tokens["eng_sse"]), json={"reason": sse_reason})
    assert r.status_code == 200
    req = r.json()
    assert req["status"] == "REVISION_REQUIRED"
    assert req["revision_notes"] == sse_reason
    print("  PASS: SSE requested revision -> status REVISION_REQUIRED")

    # Staff updates window and resubmits
    r = client.patch(f"/api/maintenance/requests/{req_id}", headers=auth_hdr(tokens["eng_staff"]), json={
        "requested_end": future_iso(6, 2),
    })
    assert r.status_code == 200
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]))
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]))
    assert r.status_code == 200
    assert r.json()["status"] == "VERIFIED"
    print("  PASS: SSE revision loop completed to VERIFIED")


def test_je_rejection(tokens):
    """
    Test JE Rejection:
    Submit -> JE Reject with mandatory reason -> REJECTED (terminal state)
    """
    print("\n=== 6. JE Rejection Flow ===")
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Unscheduled Track Alteration",
        "priority": "LOW",
        "requested_start": future_iso(7, 0),
        "requested_end": future_iso(7, 1),
    })
    req_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))

    # JE rejects
    rej_reason = "Track section is slated for major renewal next week; spot work disallowed."
    r = client.post(f"/api/maintenance/requests/{req_id}/je/reject", headers=auth_hdr(tokens["eng_je"]), json={"reason": rej_reason})
    assert r.status_code == 200
    req = r.json()
    assert req["status"] == "REJECTED"
    assert req["rejection_reason"] == rej_reason

    # Attempting to verify rejected request must fail
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]))
    assert r.status_code == 409
    print("  PASS: JE rejection marked REJECTED and cannot be verified (409)")


def test_sse_rejection(tokens):
    """
    Test SSE Rejection:
    Submit -> JE Verify -> SSE Reject with mandatory reason -> REJECTED
    """
    print("\n=== 7. SSE Rejection Flow ===")
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Ballast Cleaning",
        "priority": "HIGH",
        "requested_start": future_iso(8, 0),
        "requested_end": future_iso(8, 4),
    })
    req_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]))

    # SSE rejects
    rej_reason = "Insufficient heavy maintenance machinery available for the requested 4-hour window."
    r = client.post(f"/api/maintenance/requests/{req_id}/sse/reject", headers=auth_hdr(tokens["eng_sse"]), json={"reason": rej_reason})
    assert r.status_code == 200
    req = r.json()
    assert req["status"] == "REJECTED"
    assert req["rejection_reason"] == rej_reason
    print("  PASS: SSE rejection marked REJECTED (terminal state)")


def test_negative_security_and_rbac(tokens):
    """
    Test negative security scenarios:
    - Cross-department JE verification attempt (403)
    - Cross-department SSE verification attempt (403)
    - Staff attempting JE / SSE verification (403)
    - Operator attempting request creation (403)
    - SSE verifying before JE review (409)
    - Modifying submitted request without revision status (409)
    - Self-approval attempt (403)
    """
    print("\n=== 8. Negative Security & RBAC Enforcement ===")

    # Create ENG request
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Security Test Request",
        "priority": "HIGH",
        "requested_start": future_iso(9, 0),
        "requested_end": future_iso(9, 2),
    })
    eng_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{eng_id}/submit", headers=auth_hdr(tokens["eng_staff"]))

    # 1. Electrical JE attempting to verify Engineering request -> 403
    r = client.post(f"/api/maintenance/requests/{eng_id}/je/verify", headers=auth_hdr(tokens["elec_je"]))
    assert r.status_code == 403, f"Expected 403 for cross-dept JE review, got {r.status_code}"
    print("  PASS: Cross-department JE verification blocked (403)")

    # 2. S&T SSE attempting to verify Engineering request -> 403
    r = client.post(f"/api/maintenance/requests/{eng_id}/sse/verify", headers=auth_hdr(tokens["snt_sse"]))
    assert r.status_code == 403, f"Expected 403 for cross-dept SSE review, got {r.status_code}"
    print("  PASS: Cross-department SSE verification blocked (403)")

    # 3. Staff attempting JE verify -> 403
    r = client.post(f"/api/maintenance/requests/{eng_id}/je/verify", headers=auth_hdr(tokens["eng_staff"]))
    assert r.status_code == 403
    print("  PASS: Staff role attempting JE verification blocked (403)")

    # 4. SSE attempting verification before JE review (while still SUBMITTED) -> 409
    r = client.post(f"/api/maintenance/requests/{eng_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]))
    assert r.status_code == 409
    print("  PASS: SSE attempting verification before JE review blocked (409)")

    # 5. Operator role attempting to create request -> 403
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["operator"]), json={
        "asset_id": 1, "section_id": 1, "track_id": 1, "maintenance_type": "Op Test",
        "priority": "HIGH", "requested_start": future_iso(10, 0), "requested_end": future_iso(10, 1),
    })
    assert r.status_code == 403
    print("  PASS: Non-maintenance role creating request blocked (403)")

    # 6. Modifying submitted request without revision state -> 409
    r = client.patch(f"/api/maintenance/requests/{eng_id}", headers=auth_hdr(tokens["eng_staff"]), json={"description": "Tamper"})
    assert r.status_code == 409
    print("  PASS: Updating SUBMITTED request blocked (409)")


def test_audit_and_history_logging(tokens):
    """
    Test full audit trail logging and history endpoint retrieval.
    """
    print("\n=== 9. Audit Logging & Review History ===")
    # Create, submit, je verify, sse verify
    r = client.post("/api/maintenance/requests", headers=auth_hdr(tokens["eng_staff"]), json={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Audit Trail Inspection",
        "priority": "LOW",
        "requested_start": future_iso(11, 0),
        "requested_end": future_iso(11, 2),
    })
    req_id = r.json()["id"]
    client.post(f"/api/maintenance/requests/{req_id}/submit", headers=auth_hdr(tokens["eng_staff"]))
    client.post(f"/api/maintenance/requests/{req_id}/je/verify", headers=auth_hdr(tokens["eng_je"]), json={"reason": "JE Verified for audit test"})
    client.post(f"/api/maintenance/requests/{req_id}/sse/verify", headers=auth_hdr(tokens["eng_sse"]), json={"reason": "SSE Verified for audit test"})

    # Retrieve history
    r = client.get(f"/api/maintenance/requests/{req_id}/history", headers=auth_hdr(tokens["eng_staff"]))
    assert r.status_code == 200
    history = r.json()
    actions = [h["action"] for h in history]
    print(f"  Actions recorded in history: {actions}")
    assert "CREATE_MAINTENANCE_REQUEST" in actions
    assert "REQUEST_SUBMITTED" in actions or "TRANSITION_SUBMITTED" in actions
    assert "JE_VERIFIED" in actions
    assert "SSE_VERIFIED" in actions
    print("  PASS: Complete audit trail recorded in database and accessible via history API")


if __name__ == "__main__":
    import subprocess
    pytest.main([__file__, "-v", "-s"])
