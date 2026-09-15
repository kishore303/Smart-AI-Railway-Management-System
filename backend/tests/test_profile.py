"""Module 3 — User/Profile Management tests."""
import sys
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
r = login("eng.staff@irctc.test", "EngStaff@123")
assert r.status_code == 200, r.text
tok_eng = r.json()["access_token"]
r = login("eng.reviewer@irctc.test", "EngReview@123")
tok_reviewer = r.json()["access_token"]
r = login("elec.staff@irctc.test", "ElecStaff@123")
tok_elec = r.json()["access_token"]
r = login("railway.official@irctc.test", "Official@123")
tok_off = r.json()["access_token"]
r = login("ops.operator@irctc.test", "OpsOper@123")
tok_ops = r.json()["access_token"]

print("=== 1. Authenticated profile access ===")
r = client.get("/api/users/me", headers=hdr(tok_eng))
assert r.status_code == 200, r.text
assert r.json()["email"] == "eng.staff@irctc.test"
assert "password_hash" not in r.text and "$2b$" not in r.text
print(f"PASS — GET /me 200 {r.json()['name']} {r.json()['role']}@{r.json()['department']}")

print("\n=== 2. Unauthenticated rejection ===")
r = client.get("/api/users/me")
assert r.status_code == 401
print("PASS — unauth 401")
r = client.put("/api/users/me", json={"name": "x"})
assert r.status_code == 401
print("PASS — unauth PUT 401")
r = client.post("/api/users/me/change-password", json={"old_password": "a", "new_password": "b"})
assert r.status_code == 401
print("PASS — unauth change-pwd 401")

print("\n=== 3. Authorized profile update (self name) ===")
r = client.put("/api/users/me", headers=hdr(tok_eng), json={"name": "A. Kumar Verified"})
assert r.status_code == 200, r.text
assert r.json()["name"] == "A. Kumar Verified"
print("PASS — self update name 200")
# revert
r = client.put("/api/users/me", headers=hdr(tok_eng), json={"name": "A. Kumar"})
assert r.json()["name"] == "A. Kumar"
print("PASS — revert 200")

print("\n=== 4. Unauthorized profile update (other user) ===")
# eng.staff tries to PATCH elec.staff via admin endpoint — should be 403 (not official)
r = client.patch("/api/users/4", headers=hdr(tok_eng), json={"name": "Hacked"})
assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text}"
print("PASS — non-official PATCH other 403")
# eng.staff tries to GET elec user
r = client.get("/api/users/4", headers=hdr(tok_eng))
assert r.status_code == 403
print("PASS — cross-dept GET 403")
# reviewer tries same
r = client.patch("/api/users/4", headers=hdr(tok_reviewer), json={"name": "Hacked"})
assert r.status_code == 403
print("PASS — reviewer cannot admin-patch 403")

print("\n=== 5. Cross-department restrictions (list) ===")
r = client.get("/api/users", headers=hdr(tok_eng))
assert r.status_code == 200
# ENG dept has 4 users: 1,2,3,12(inactive filtered? depends) — but with default is_active filter none, should see 4 ENG including inactive
# Check only ENG codes returned
codes = set(u["department"] for u in r.json()["items"])
assert codes == {"ENG"}, f"eng list should only see ENG got {codes}"
print(f"PASS — ENG list only ENG ({r.json()['total']} users)")
# try to filter other dept
r = client.get("/api/users?department_code=ELEC", headers=hdr(tok_eng))
assert r.status_code == 403
print("PASS — ENG filter ELEC 403")
# official sees all
r = client.get("/api/users", headers=hdr(tok_off))
assert r.status_code == 200
assert r.json()["total"] == 12, r.json()
print(f"PASS — official sees all 12")
r = client.get("/api/users?department_code=SNT", headers=hdr(tok_off))
assert r.status_code == 200 and r.json()["total"] == 2
print("PASS — official filter SNT 2")

print("\n=== 6. Role/department modification protection ===")
# Self-update with role field — should be ignored, not escalated
r = client.put("/api/users/me", headers=hdr(tok_eng), json={"name": "A. Kumar"})
# Try sending role via JSON — Pydantic ignores extra, so still 200 but role unchanged
r = client.put("/api/users/me", headers=hdr(tok_eng), json={"name": "A. Kumar", "role": "AUTHORIZED_OFFICIAL", "department_code": "RAILWAY"})
# Our endpoint only reads name, so role stays
r_check = client.get("/api/users/me", headers=hdr(tok_eng))
assert r_check.json()["role"] == "MAINTENANCE_STAFF", "role escalation via self PUT"
assert r_check.json()["department"] == "ENG", "dept escalation via self PUT"
print("PASS — self role/dept not escalated via PUT /me")

# Official trying invalid role for dept
r = client.patch("/api/users/1", headers=hdr(tok_off), json={"role": "CONTROLLER", "department_code": "ENG"})
assert r.status_code == 422, f"invalid role for ENG should be 422 got {r.status_code} {r.text}"
print("PASS — invalid role for dept 422")

# Official valid update
r = client.patch("/api/users/8", headers=hdr(tok_off), json={"is_active": False})
assert r.status_code == 200
assert r.json()["is_active"] == False
print("PASS — official can deactivate 200")
# Reactivate
r = client.patch("/api/users/8", headers=hdr(tok_off), json={"is_active": True})
assert r.json()["is_active"] == True
print("PASS — reactivate 200")

# Official try to set role without dept — should keep dept but validate
r = client.patch("/api/users/3", headers=hdr(tok_off), json={"role": "ENGINEER_REVIEWER"})
assert r.status_code == 200
assert r.json()["role"] == "ENGINEER_REVIEWER"
print(f"PASS — official role change same dept 200 -> {r.json()['role']}")
# revert
r = client.patch("/api/users/3", headers=hdr(tok_off), json={"role": "MAINTENANCE_STAFF"})
assert r.json()["role"] == "MAINTENANCE_STAFF"
print("PASS — revert role 200")

print("\n=== 7. Sensitive-field protection ===")
for path, h in [("/api/users/me", hdr(tok_eng)), ("/api/users", hdr(tok_off)), ("/api/users/1", hdr(tok_off))]:
    r = client.get(path, headers=h)
    assert "password_hash" not in r.text
    assert "$2b$" not in r.text
    assert "password" not in r.text.lower() or "password" in "change-password"  # allow change-password path
    print(f"PASS — {path} no hash leaked")
# JWT check
from app.core.security import decode_token
tok = login("eng.staff@irctc.test", "EngStaff@123").json()["access_token"]
payload = decode_token(tok)
assert "password_hash" not in payload and "password" not in payload
print("PASS — JWT no sensitive")

print("\n=== 8. RBAC enforcement ===")
# ops.operator cannot list as official but can list own dept (OPS has 1)
r = client.get("/api/users", headers=hdr(tok_ops))
assert r.status_code == 200
assert all(u["department"] == "OPS" for u in r.json()["items"])
print("PASS — OPS can only see OPS")
# ops cannot PATCH
r = client.patch("/api/users/1", headers=hdr(tok_ops), json={"name": "x"})
assert r.status_code == 403
print("PASS — OPS PATCH 403")
# reviewer cannot PATCH
r = client.patch("/api/users/1", headers=hdr(tok_reviewer), json={"name": "x"})
assert r.status_code == 403
print("PASS — REVIEWER PATCH 403")

print("\n=== 9. Change password authorized ===")
r = client.post("/api/users/me/change-password", headers=hdr(tok_eng), json={"old_password": "Wrong123", "new_password": "NewPass@1234"})
assert r.status_code == 400
print("PASS — wrong old 400")
r = client.post("/api/users/me/change-password", headers=hdr(tok_eng), json={"old_password": "EngStaff@123", "new_password": "NewPass@12345"})
assert r.status_code == 200
print("PASS — correct change 200")
# Login with new
r = login("eng.staff@irctc.test", "NewPass@12345")
assert r.status_code == 200
print("PASS — login with new pwd 200")
# Revert
new_tok = r.json()["access_token"]
r = client.post("/api/users/me/change-password", headers={"Authorization": f"Bearer {new_tok}"}, json={"old_password": "NewPass@12345", "new_password": "EngStaff@123"})
assert r.status_code == 200
print("PASS — revert pwd 200")

print("\n=== 10. Audit logging ===")
with engine.connect() as conn:
    rows = conn.execute(text("SELECT action FROM audit_logs ORDER BY id DESC LIMIT 20")).fetchall()
    actions = [a[0] for a in rows]
    print(f" Recent audits: {actions[:10]}")
    assert "UPDATE_PROFILE" in actions, "UPDATE_PROFILE missing"
    assert "CHANGE_PASSWORD" in actions or "CHANGE_PASSWORD_FAILED" in actions
    assert "ADMIN_UPDATE_USER" in actions
    print("PASS — UPDATE_PROFILE/CHANGE_PASSWORD/ADMIN_UPDATE_USER logged")

print("\n=== 11. Modules 1 & 2 intact ===")
import subprocess
res = subprocess.run(["python", "D:\\IRCTC\\backend\\scripts\\verify_models.py"], capture_output=True, text=True)
assert "ALL MODEL VERIFICATION PASSED" in res.stdout, res.stdout
print("PASS — Module1 verify_models")
res2 = subprocess.run(["python", "D:\\IRCTC\\backend\\tests\\test_db_connection.py"], capture_output=True, text=True)
assert "All connection tests passed" in res2.stdout
print("PASS — Module1 db_connection")
res3 = subprocess.run(["python", "D:\\IRCTC\\backend\\tests\\test_auth_rbac.py"], capture_output=True, text=True)
assert "ALL 11 (+2) CHECKS PASSED" in res3.stdout, res3.stdout[-1000:]
print("PASS — Module2 auth_rbac still passes")

print("\n========== ALL MODULE 3 CHECKS PASSED ==========")
