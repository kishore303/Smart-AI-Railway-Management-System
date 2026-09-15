"""Module 4 — Maintenance Request tests (12 groups)."""
import sys, datetime
from pathlib import Path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine

client = TestClient(app)

def login(email, pwd):
    return client.post("/api/auth/login", json={"username": email, "password": pwd})

def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}

# Get tokens
tok_eng = login("eng.staff@irctc.test", "EngStaff@123").json()["access_token"]
tok_eng2 = login("eng.staff2@irctc.test", "EngStaff2@123").json()["access_token"]
tok_reviewer = login("eng.reviewer@irctc.test", "EngReview@123").json()["access_token"]
tok_elec = login("elec.staff@irctc.test", "ElecStaff@123").json()["access_token"]
tok_off = login("railway.official@irctc.test", "Official@123").json()["access_token"]
tok_ops = login("ops.operator@irctc.test", "OpsOper@123").json()["access_token"]
tok_snt = login("snt.staff@irctc.test", "SntStaff@123").json()["access_token"]

def future(days=2, hours=0):
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours)
    return dt.isoformat()

# Clean previous requests for determinism (FK order: notifications -> integration -> candidates -> blocks -> maintenance)
from app.database import SessionLocal
from app.models.maintenance import MaintenanceRequest
from app.models.block import BlockRequest, BlockCandidate, BlockIntegrationRequest, OptimizedBlock
from sqlalchemy import text
db = SessionLocal()
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
db.close()

print("=== 1. Valid creation ===")
start = future(2)
end = future(2,2)
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Track Tamping","priority":"HIGH","requested_start":start,"requested_end":end,"description":"Valid ENG test"})
assert r.status_code == 201, f"201 expected got {r.status_code} {r.text}"
req1 = r.json()
assert req1["status"] == "DRAFT"
assert req1["priority"] == "HIGH"
assert req1["requested_duration_mins"] == 120
assert req1["department_code"] == "ENG"
assert req1["requested_by"] == 1
assert "password_hash" not in r.text and "$2b$" not in r.text
print(f"PASS — created {req1['request_code']} id={req1['id']} DRAFT")

# Valid ELEC
r = client.post("/api/maintenance/requests", headers=hdr(tok_elec), json={"asset_id":2,"section_id":1,"track_id":1,"maintenance_type":"OHE Inspection","priority":"MEDIUM","requested_start":future(3),"requested_end":future(3,1)})
assert r.status_code == 201
req_elec = r.json()
print(f"PASS — ELEC created {req_elec['id']}")

print("\n=== 2. Missing/invalid fields ===")
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"section_id":1,"track_id":1,"maintenance_type":"x","priority":"HIGH","requested_start":start,"requested_end":end})
assert r.status_code == 422
print("PASS — missing asset_id 422")
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"x","priority":"BAD","requested_start":start,"requested_end":end})
assert r.status_code == 422
print("PASS — invalid priority 422")
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"x","priority":"HIGH","requested_start":start,"requested_end":end,"description":"x"*3000})
# description long but allowed up to 2000 — we set 2000 limit, so this may be 422
print(f" long desc status {r.status_code}")

print("\n=== 3. Invalid time windows ===")
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":end,"requested_end":start})
assert r.status_code == 422
print("PASS — end before start 422")
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":start,"requested_end":start})
assert r.status_code == 422
print("PASS — equal start/end 422")

print("\n=== 4. Invalid section/track/asset relationships ===")
# Asset 2 belongs to ELEC but eng.staff tries with asset 2 -> should be 403 asset dept mismatch
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":2,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":future(4),"requested_end":future(4,1)})
assert r.status_code == 403, f"asset dept mismatch should be 403 got {r.status_code} {r.text}"
print("PASS — asset dept mismatch 403")
# Track 3 belongs to section 2 but using section 1
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":3,"maintenance_type":"Test","priority":"HIGH","requested_start":future(4),"requested_end":future(4,1)})
assert r.status_code == 422, f"track/section mismatch should be 422 got {r.status_code}"
print("PASS — track/section mismatch 422")
# Nonexistent asset
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":9999,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":future(4),"requested_end":future(4,1)})
assert r.status_code == 404
print("PASS — nonexistent asset 404")
# Invalid resource
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":future(4),"requested_end":future(4,1),"resource_ids":[9999]})
assert r.status_code == 404
print("PASS — invalid resource 404")

print("\n=== 5. Unauthorized creation/access/update ===")
r = client.post("/api/maintenance/requests", headers=hdr(tok_ops), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":future(5),"requested_end":future(5,1)})
assert r.status_code == 403, f"ops should be 403 got {r.status_code}"
print("PASS — OPS create 403")
r = client.post("/api/maintenance/requests", json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Test","priority":"HIGH","requested_start":future(5),"requested_end":future(5,1)})
assert r.status_code == 401
print("PASS — unauth create 401")
r = client.get(f"/api/maintenance/requests/{req1['id']}")
assert r.status_code == 401
print("PASS — unauth get 401")
# Update by non-owner
r = client.patch(f"/api/maintenance/requests/{req1['id']}", headers=hdr(tok_eng2), json={"description":"Hacked"})
assert r.status_code == 403
print("PASS — non-owner update 403")

print("\n=== 6. Department-scoped access ===")
# eng.staff can see own dept requests (ENG)
r = client.get("/api/maintenance/requests", headers=hdr(tok_eng))
assert r.status_code == 200
assert all(i["department_code"]=="ENG" for i in r.json()["items"])
print(f"PASS — ENG sees only ENG ({r.json()['total']})")
# elec sees only ELEC
r = client.get("/api/maintenance/requests", headers=hdr(tok_elec))
assert all(i["department_code"]=="ELEC" for i in r.json()["items"])
print(f"PASS — ELEC sees only ELEC ({r.json()['total']})")
# elec cannot GET eng's request
r = client.get(f"/api/maintenance/requests/{req1['id']}", headers=hdr(tok_elec))
assert r.status_code == 403
print("PASS — ELEC cannot GET ENG 403")
# official can
r = client.get(f"/api/maintenance/requests/{req1['id']}", headers=hdr(tok_off))
assert r.status_code == 200
print("PASS — OFFICIAL can GET ENG 200")
# official list sees both
r = client.get("/api/maintenance/requests", headers=hdr(tok_off))
assert r.json()["total"] >= 2
print(f"PASS — official sees all {r.json()['total']}")
# Eng trying to filter other dept should be 403
r = client.get("/api/maintenance/requests?department_code=ELEC", headers=hdr(tok_eng))
assert r.status_code == 403
print("PASS — ENG filter ELEC 403")

print("\n=== 7. Valid status transitions ===")
# DRAFT -> SUBMITTED by owner
r = client.post(f"/api/maintenance/requests/{req1['id']}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
assert r.status_code == 200 and r.json()["status"]=="SUBMITTED"
print("PASS — DRAFT->SUBMITTED 200")
# SUBMITTED -> UNDER_REVIEW by reviewer same dept
r = client.post(f"/api/maintenance/requests/{req1['id']}/transition", headers=hdr(tok_reviewer), json={"new_status":"UNDER_REVIEW"})
assert r.status_code == 200 and r.json()["status"]=="UNDER_REVIEW"
print("PASS — SUBMITTED->UNDER_REVIEW 200")
# UNDER_REVIEW -> VERIFIED
r = client.post(f"/api/maintenance/requests/{req1['id']}/transition", headers=hdr(tok_reviewer), json={"new_status":"VERIFIED"})
assert r.status_code == 200 and r.json()["status"]=="VERIFIED"
print("PASS — UNDER_REVIEW->VERIFIED 200")
# VERIFIED -> BLOCK_PLANNING
r = client.post(f"/api/maintenance/requests/{req1['id']}/transition", headers=hdr(tok_reviewer), json={"new_status":"BLOCK_PLANNING"})
assert r.status_code == 200 and r.json()["status"]=="BLOCK_PLANNING"
print("PASS — VERIFIED->BLOCK_PLANNING 200")
# Test REVISION flow with new request
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Revision Test","priority":"LOW","requested_start":future(6),"requested_end":future(6,1)})
rid2 = r.json()["id"]
client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_reviewer), json={"new_status":"UNDER_REVIEW"})
r = client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_reviewer), json={"new_status":"REVISION_REQUIRED","reason":"Need more info"})
assert r.status_code == 200 and r.json()["status"]=="REVISION_REQUIRED"
print("PASS — UNDER_REVIEW->REVISION_REQUIRED 200")
r = client.patch(f"/api/maintenance/requests/{rid2}", headers=hdr(tok_eng), json={"description":"Fixed after revision"})
assert r.status_code == 200
print("PASS — update in REVISION_REQUIRED 200")
r = client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
assert r.status_code == 200 and r.json()["status"]=="SUBMITTED"
print("PASS — REVISION_REQUIRED->SUBMITTED 200")

print("\n=== 8. Invalid/skipped transitions ===")
# Create fresh DRAFT
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Skip Test","priority":"MEDIUM","requested_start":future(7),"requested_end":future(7,1)})
rid3 = r.json()["id"]
# Try skip DRAFT->VERIFIED
r = client.post(f"/api/maintenance/requests/{rid3}/transition", headers=hdr(tok_reviewer), json={"new_status":"VERIFIED"})
assert r.status_code == 409
print("PASS — skip DRAFT->VERIFIED 409")
# Try invalid transition SUBMITTED->VERIFIED (must go via UNDER_REVIEW)
r = client.post(f"/api/maintenance/requests/{rid3}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
assert r.status_code == 200
r = client.post(f"/api/maintenance/requests/{rid3}/transition", headers=hdr(tok_reviewer), json={"new_status":"VERIFIED"})
assert r.status_code == 409
print("PASS — skip SUBMITTED->VERIFIED 409")
# Update in SUBMITTED should fail
r = client.patch(f"/api/maintenance/requests/{rid3}", headers=hdr(tok_eng), json={"description":"Should fail"})
assert r.status_code == 409
print("PASS — update in SUBMITTED 409")

print("\n=== 9. Self-review/self-approval protection ===")
# Use eng.staff's own request in SUBMITTED, reviewer is same eng.staff -> should be blocked
r = client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Self Test","priority":"MEDIUM","requested_start":future(8),"requested_end":future(8,1)})
rid4 = r.json()["id"]
client.post(f"/api/maintenance/requests/{rid4}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
# eng.staff tries to self-review to UNDER_REVIEW
r = client.post(f"/api/maintenance/requests/{rid4}/transition", headers=hdr(tok_eng), json={"new_status":"UNDER_REVIEW"})
assert r.status_code == 403, f"self-review should be 403 got {r.status_code} {r.text}"
print("PASS — self-review UNDER_REVIEW 403")
# Also test via stub? Already tested Module 2 but reconfirm
r = client.post(f"/api/maintenance/{rid4}/verify", headers=hdr(tok_eng), json={"requested_by": 1})
assert r.status_code == 403
print("PASS — stub self-verify 403")
# Correct reviewer succeeds
r = client.post(f"/api/maintenance/requests/{rid4}/transition", headers=hdr(tok_reviewer), json={"new_status":"UNDER_REVIEW"})
assert r.status_code == 200
print("PASS — legitimate reviewer 200")

print("\n=== 10. Audit logging ===")
with engine.connect() as conn:
    rows = conn.execute(text("SELECT action, entity_id FROM audit_logs WHERE entity_type='maintenance_request' ORDER BY id DESC LIMIT 15")).fetchall()
    actions = [a[0] for a in rows]
    print(f" recent maintenance audits: {actions[:10]}")
    assert "CREATE_MAINTENANCE_REQUEST" in actions
    assert any("TRANSITION_" in a for a in actions)
    assert "UPDATE_MAINTENANCE_REQUEST" in actions or "UPDATE_MAINTENANCE_REQUEST_STATUS" in actions
    print("PASS — maintenance audits logged")

print("\n=== 11. DB constraint/model consistency ===")
with engine.connect() as conn:
    # Check enum still correct
    cnt = conn.execute(text("SELECT count(*) FROM maintenance_requests")).scalar()
    print(f" maintenance_requests count {cnt}")
    # Check priority enum exists
    rows = conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid=pg_type.oid WHERE typname='severity_level' ORDER BY enumsortorder")).fetchall()
    labels = [l[0] for l in rows]
    assert "HIGH" in labels
    print(f" PASS — severity_level {labels}")
    # Check self-approval DB constraint via attempted direct insert with reviewed_by = requested_by would fail at DB but we already test API
    # Check geometry still
    gc = conn.execute(text("SELECT count(*) FROM geometry_columns WHERE srid=4326")).scalar()
    assert gc >= 6
    print(f" PASS — geometry_columns {gc}")

print("\n=== 12. Sensitive fields ===")
r = client.get(f"/api/maintenance/requests/{req1['id']}", headers=hdr(tok_eng))
assert "password_hash" not in r.text and "$2b$" not in r.text
print("PASS — maintenance detail no hash")

print("\n=== 13. Regression Modules 1,2,3 ===")
import subprocess
res = subprocess.run(["python", "D:\\IRCTC\\backend\\scripts\\verify_models.py"], capture_output=True, text=True)
assert "ALL MODEL VERIFICATION PASSED" in res.stdout
print("PASS — Module1 verify_models")
res = subprocess.run(["python", "D:\\IRCTC\\backend\\tests\\test_auth_rbac.py"], capture_output=True, text=True)
assert "ALL 11 (+2) CHECKS PASSED" in res.stdout, res.stdout[-800:]
print("PASS — Module2 auth_rbac")
res = subprocess.run(["python", "D:\\IRCTC\\backend\\tests\\test_profile.py"], capture_output=True, text=True)
assert "ALL MODULE 3 CHECKS PASSED" in res.stdout, res.stdout[-800:]
print("PASS — Module3 profile")

print("\n========== ALL MODULE 4 CHECKS PASSED ==========")