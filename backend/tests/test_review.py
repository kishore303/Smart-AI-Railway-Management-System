"""Module 5 — Review & Verification tests."""
import sys, datetime
from pathlib import Path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine, SessionLocal
from app.models.maintenance import MaintenanceRequest

client = TestClient(app)

def login(email,pwd):
    return client.post("/api/auth/login", json={"username":email,"password":pwd})

def tok(email,pwd):
    r=login(email,pwd)
    assert r.status_code==200, r.text
    return r.json()["access_token"]

def hdr(t): return {"Authorization": f"Bearer {t}"}
def fut(days): return (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=days)).isoformat()
def fut2(days,h): return (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=days, hours=h)).isoformat()

tok_eng = tok("eng.staff@irctc.test","EngStaff@123")
tok_rev = tok("eng.reviewer@irctc.test","EngReview@123")
tok_elec_rev = tok("elec.reviewer@irctc.test","ElecReview@123")
tok_elec_staff = tok("elec.staff@irctc.test","ElecStaff@123")
tok_off = tok("railway.official@irctc.test","Official@123")
tok_ops = tok("ops.operator@irctc.test","OpsOper@123")

# Clean (FK order: safety -> notifications -> integration -> candidates -> optimized sources -> optimized -> requests -> predictions -> maintenance)
from app.database import SessionLocal as SL2
from app.models.maintenance import MaintenanceRequest as MR2
from app.models.block import BlockRequest as BR2, BlockCandidate as BC2, BlockIntegrationRequest as BIR2, OptimizedBlock as OB2
from sqlalchemy import text
db2 = SL2()
db2.execute(text("DELETE FROM safety_validations"))
db2.execute(text("DELETE FROM simulations"))
db2.execute(text("DELETE FROM notifications WHERE optimized_block_id IS NOT NULL"))
db2.execute(text("DELETE FROM notifications WHERE integration_request_id IS NOT NULL"))
db2.query(BIR2).delete()
db2.query(BC2).delete()
db2.execute(text("DELETE FROM optimized_block_sources"))
db2.query(OB2).delete()
db2.query(BR2).delete()
db2.execute(text("DELETE FROM maintenance_predictions"))
db2.query(MR2).delete()
db2.commit()
db2.close()


print("=== 1. Valid review workflow (VERIFY) ===")
r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Valid Review","priority":"HIGH","requested_start":fut(20),"requested_end":fut2(20,2)})
assert r.status_code==201, r.text
rid=r.json()["id"]
print(f" created {rid} DRAFT")
r=client.post(f"/api/maintenance/requests/{rid}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
assert r.json()["status"]=="SUBMITTED"
print(" SUBMITTED 200")
r=client.post(f"/api/maintenance/requests/{rid}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
assert r.json()["status"]=="UNDER_REVIEW"
print(" UNDER_REVIEW 200")
r=client.post(f"/api/maintenance/requests/{rid}/review", headers=hdr(tok_rev), json={"action":"VERIFY"})
assert r.status_code==200 and r.json()["status"]=="VERIFIED"
assert r.json()["reviewed_by"] is not None
print(f" VERIFY 200 -> VERIFIED reviewed_by={r.json()['reviewed_by']}")

print("\n=== 2. Revision workflow ===")
r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Revision Flow","priority":"MEDIUM","requested_start":fut(21),"requested_end":fut2(21,1)})
rid2=r.json()["id"]
client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
r=client.post(f"/api/maintenance/requests/{rid2}/review", headers=hdr(tok_rev), json={"action":"REVISION_REQUIRED","reason":"Add safety plan and resource list"})
assert r.status_code==200 and r.json()["status"]=="REVISION_REQUIRED"
assert "safety" in (r.json()["revision_notes"] or "")
print(" REVISION_REQUIRED 200 revision_notes saved")
# Requester can update in REVISION
r=client.patch(f"/api/maintenance/requests/{rid2}", headers=hdr(tok_eng), json={"description":"Updated with safety plan"})
assert r.status_code==200
print(" PATCH in REVISION 200")
r=client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
assert r.json()["status"]=="SUBMITTED"
print(" REVISION->SUBMITTED 200")
# Review again and verify
client.post(f"/api/maintenance/requests/{rid2}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
r=client.post(f"/api/maintenance/requests/{rid2}/review", headers=hdr(tok_rev), json={"action":"VERIFY"})
assert r.json()["status"]=="VERIFIED"
print(" Re-VERIFY 200")

print("\n=== 3. Rejection workflow ===")
r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Reject Flow","priority":"LOW","requested_start":fut(22),"requested_end":fut2(22,1)})
rid3=r.json()["id"]
client.post(f"/api/maintenance/requests/{rid3}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
client.post(f"/api/maintenance/requests/{rid3}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
r=client.post(f"/api/maintenance/requests/{rid3}/review", headers=hdr(tok_rev), json={"action":"REJECT","reason":"Duplicate work"})
assert r.status_code==200 and r.json()["status"]=="REJECTED"
assert r.json()["rejection_reason"]=="Duplicate work"
print(" REJECT 200 rejection_reason saved")

print("\n=== 4. Unauthorized review attempts ===")
# STAFF cannot review
r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Unauth","priority":"HIGH","requested_start":fut(23),"requested_end":fut2(23,1)})
rid4=r.json()["id"]
client.post(f"/api/maintenance/requests/{rid4}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
client.post(f"/api/maintenance/requests/{rid4}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
r=client.post(f"/api/maintenance/requests/{rid4}/review", headers=hdr(tok_eng), json={"action":"VERIFY"})
assert r.status_code==403
print(" STAFF review 403")
# OPS cannot review
r=client.post(f"/api/maintenance/requests/{rid4}/review", headers=hdr(tok_ops), json={"action":"VERIFY"})
assert r.status_code==403
print(" OPS review 403")
# Unauthenticated
r=client.post(f"/api/maintenance/requests/{rid4}/review", json={"action":"VERIFY"})
assert r.status_code==401
print(" unauth review 401")
# ELEC reviewer cannot review ENG request
r=client.post(f"/api/maintenance/requests/{rid4}/review", headers=hdr(tok_elec_rev), json={"action":"VERIFY"})
assert r.status_code==403
print(" cross-dept reviewer 403")

print("\n=== 5. Self-review prevention ===")
# ENG reviewer creates own request and tries to self-review (must be blocked via self-approval)
r=client.post("/api/maintenance/requests", headers=hdr(tok_rev), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"SelfReview EngRev","priority":"HIGH","requested_start":fut(24),"requested_end":fut2(24,1)})
rid5b=r.json()["id"]
if r.status_code==201:
    client.post(f"/api/maintenance/requests/{rid5b}/transition", headers=hdr(tok_rev), json={"new_status":"SUBMITTED"})
    r=client.post(f"/api/maintenance/requests/{rid5b}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
    assert r.status_code==403 and "Self-approval" in r.text
    print(" self UNDER_REVIEW via creator=reviewer 403 Self-approval")
    # Cleanup: have different reviewer? Use official to move? But ENG reviewer self-blocked — use different path: create via staff then test staff cannot review via transition (role) and via dedicated review (self+role)
    # Dedicated self-review test: staff's request reviewed by staff via /review endpoint should be 403
    r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Self2","priority":"HIGH","requested_start":fut(24),"requested_end":fut2(24,1)})
    rid5=r.json()["id"]
    client.post(f"/api/maintenance/requests/{rid5}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
    client.post(f"/api/maintenance/requests/{rid5}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
    # staff tries dedicated review on his own after it's UNDER_REVIEW
    r=client.post(f"/api/maintenance/requests/{rid5}/review", headers=hdr(tok_eng), json={"action":"VERIFY"})
    assert r.status_code==403
    print(" self VERIFY via dedicated endpoint 403")
    # Legitimate reviewer succeeds
    r=client.post(f"/api/maintenance/requests/{rid5}/review", headers=hdr(tok_rev), json={"action":"VERIFY"})
    assert r.status_code==200
    print(" legit reviewer VERIFY 200")
else:
    # Fallback: staff cannot UNDER_REVIEW due to role — also 403 (role check)
    r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"Self","priority":"HIGH","requested_start":fut(24),"requested_end":fut2(24,1)})
    rid5=r.json()["id"]
    client.post(f"/api/maintenance/requests/{rid5}/transition", headers=hdr(tok_eng), json={"new_status":"SUBMITTED"})
    r=client.post(f"/api/maintenance/requests/{rid5}/transition", headers=hdr(tok_eng), json={"new_status":"UNDER_REVIEW"})
    assert r.status_code==403
    print(" self UNDER_REVIEW via staff role 403")
    client.post(f"/api/maintenance/requests/{rid5}/transition", headers=hdr(tok_rev), json={"new_status":"UNDER_REVIEW"})
    r=client.post(f"/api/maintenance/requests/{rid5}/review", headers=hdr(tok_eng), json={"action":"VERIFY"})
    assert r.status_code==403
    print(" self VERIFY 403")
    r=client.post(f"/api/maintenance/requests/{rid5}/review", headers=hdr(tok_rev), json={"action":"VERIFY"})
    assert r.status_code==200
    print(" legit reviewer VERIFY 200")

print("\n=== 6. Review history & comments ===")
r=client.get(f"/api/maintenance/requests/{rid}/history", headers=hdr(tok_eng))
assert r.status_code==200
hist=r.json()
print(f" history len {len(hist)} for {rid}: {[h['action'] for h in hist[:6]]}")
assert any(h["action"]=="VERIFY_MAINTENANCE_REQUEST" for h in hist)
assert any(h["action"]=="CREATE_MAINTENANCE_REQUEST" for h in hist)
print(" PASS history contains VERIFY and CREATE")
# revision_notes history
r=client.get(f"/api/maintenance/requests/{rid2}/history", headers=hdr(tok_eng))
assert any("REVISION_REQUIRED" in h["action"] for h in r.json())
print(" PASS revision history")
# cross-dept history denied for elec staff trying to see eng history? elec is different dept
r=client.get(f"/api/maintenance/requests/{rid}/history", headers=hdr(tok_elec_staff))
assert r.status_code==403
print(" PASS cross-dept history 403")
# official can see
r=client.get(f"/api/maintenance/requests/{rid}/history", headers=hdr(tok_off))
assert r.status_code==200
print(" PASS official history 200")

print("\n=== 7. Review queue ===")
# After previous verifies, queue should have rid4 still UNDER_REVIEW plus any SUBMITTED pending
r=client.get("/api/maintenance/review/queue", headers=hdr(tok_rev))
assert r.status_code==200
print(f" ENG reviewer queue total {r.json()['total']} ids {[i['id'] for i in r.json()['items']]}")
assert all(i["department_code"]=="ENG" for i in r.json()["items"])
print(" PASS queue only ENG")
# ELEC reviewer sees only ELEC queue
r=client.post("/api/maintenance/requests", headers=hdr(tok_elec_staff), json={"asset_id":2,"section_id":1,"track_id":1,"maintenance_type":"ELEC Queue","priority":"HIGH","requested_start":fut(25),"requested_end":fut2(25,1)})
rid_e=r.json()["id"]
client.post(f"/api/maintenance/requests/{rid_e}/transition", headers=hdr(tok_elec_staff), json={"new_status":"SUBMITTED"})
r=client.get("/api/maintenance/review/queue", headers=hdr(tok_elec_rev))
assert r.status_code==200
assert any(i["id"]==rid_e for i in r.json()["items"])
print(" PASS ELEC queue contains ELEC request")
# ENG reviewer should not see ELEC in queue
r=client.get("/api/maintenance/review/queue", headers=hdr(tok_rev))
assert all(i["id"]!=rid_e for i in r.json()["items"])
print(" PASS ENG queue not containing ELEC")
# Non-reviewer cannot access queue
r=client.get("/api/maintenance/review/queue", headers=hdr(tok_eng))
assert r.status_code==403
print(" PASS staff queue 403")
r=client.get("/api/maintenance/review/queue", headers=hdr(tok_ops))
assert r.status_code==403
print(" PASS ops queue 403")

print("\n=== 8. Audit logging ===")
with engine.connect() as conn:
    rows=conn.execute(text("SELECT action FROM audit_logs WHERE entity_type='maintenance_request' ORDER BY id DESC LIMIT 50")).fetchall()
    acts=[a[0] for a in rows]
    print(f" audits {acts[:20]}")
    assert "VERIFY_MAINTENANCE_REQUEST" in acts
    assert "REJECT_MAINTENANCE_REQUEST" in acts
    assert "REVISION_REQUIRED" in acts or "TRANSITION_REVISION_REQUIRED" in acts
    print(" PASS audit actions present")

print("\n=== 9. Regression 1-4 ===")
import subprocess
res=subprocess.run([sys.executable, str(backend_dir / "scripts" / "verify_models.py")], capture_output=True, text=True)
assert "ALL MODEL VERIFICATION PASSED" in res.stdout
print(" PASS Module1")
res=subprocess.run([sys.executable, str(backend_dir / "tests" / "test_auth_rbac.py")], capture_output=True, text=True)
assert "ALL 11 (+2) CHECKS PASSED" in res.stdout, res.stdout[-800:]
print(" PASS Module2")
res=subprocess.run([sys.executable, str(backend_dir / "tests" / "test_profile.py")], capture_output=True, text=True)
assert "ALL MODULE 3 CHECKS PASSED" in res.stdout, res.stdout[-800:]
print(" PASS Module3")
res=subprocess.run([sys.executable, str(backend_dir / "tests" / "test_maintenance.py")], capture_output=True, text=True)
assert "ALL MODULE 4 CHECKS PASSED" in res.stdout, res.stdout[-800:]
print(" PASS Module4")

print("\n========== ALL MODULE 5 CHECKS PASSED ==========")

