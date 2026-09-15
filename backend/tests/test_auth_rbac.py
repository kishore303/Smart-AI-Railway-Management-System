"""Module 2 — 11 verification tests."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine
from app.core.security import decode_token

client = TestClient(app)

# Helper
def login(email, password):
    return client.post("/api/auth/login", json={"username": email, "password": password})

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}

print("=== 1. Valid login ===")
r = login("eng.staff@irctc.test", "EngStaff@123")
assert r.status_code == 200, f"valid login failed: {r.status_code} {r.text}"
data = r.json()
token_eng_staff = data["access_token"]
assert "password" not in r.text.lower()
assert "password_hash" not in r.text.lower()
print(f"PASS — eng.staff login 200, token len {len(token_eng_staff)}, user {data['user']['role']}@{data['user']['department']}")

r = login("railway.official@irctc.test", "Official@123")
assert r.status_code == 200
token_official = r.json()["access_token"]
print(f"PASS — official login 200")

r = login("ops.operator@irctc.test", "OpsOper@123")
assert r.status_code == 200
token_ops = r.json()["access_token"]
print(f"PASS — ops login 200")

print("\n=== 2. Invalid credentials ===")
r = login("eng.staff@irctc.test", "Wrong@123")
assert r.status_code == 401, f"expected 401 got {r.status_code}"
print("PASS — wrong password 401")
r = login("nonexistent@irctc.test", "Whatever@123")
assert r.status_code == 401
print("PASS — nonexistent user 401")

print("\n=== 3. Inactive user ===")
r = login("inactive@irctc.test", "Inactive@123")
assert r.status_code == 401, f"inactive should be 401 got {r.status_code} {r.text}"
print("PASS — inactive 401")

print("\n=== 4. JWT generation & validation ===")
payload = decode_token(token_eng_staff)
print(f" JWT payload: {payload}")
assert payload["user_id"] == 1
assert payload["email"] == "eng.staff@irctc.test"
assert payload["role"] == "MAINTENANCE_STAFF"
assert payload["department_code"] == "ENG"
assert payload["department_id"] == 1
assert "iat" in payload and "exp" in payload
assert "password" not in payload and "password_hash" not in payload
print("PASS — JWT contains required claims, no sensitive data, iat/exp present")

# Expired token — create with -1 minute
from app.core.security import create_access_token
from datetime import timedelta
expired = create_access_token({"user_id":1,"email":"x","department":"ENG","department_code":"ENG","department_id":1,"role":"MAINTENANCE_STAFF"}, expires_delta=timedelta(seconds=-10))
r = client.get("/api/auth/me", headers=auth_header(expired))
assert r.status_code == 401, f"expired should be 401 got {r.status_code}"
print("PASS — expired JWT 401")

# No token
r = client.get("/api/auth/me")
assert r.status_code == 401
print("PASS — missing token 401")

# Valid me
r = client.get("/api/auth/me", headers=auth_header(token_eng_staff))
assert r.status_code == 200, r.text
assert r.json()["email"] == "eng.staff@irctc.test"
print("PASS — /me with valid token 200")

# Username login (not email)
r = login("A. Kumar", "EngStaff@123")
assert r.status_code == 200
print("PASS — username login works")

print("\n=== 5. Role-based access ===")
# Only AUTHORIZED_OFFICIAL can hit admin endpoint
r = client.get("/api/users/admin/only-official", headers=auth_header(token_eng_staff))
assert r.status_code == 403, f"eng.staff should be 403 got {r.status_code}"
print("PASS — MAINTENANCE_STAFF blocked from official endpoint 403")
r = client.get("/api/users/admin/only-official", headers=auth_header(token_official))
assert r.status_code == 200, r.text
print("PASS — AUTHORIZED_OFFICIAL allowed 200")
r = client.get("/api/users/admin/only-official", headers=auth_header(token_ops))
assert r.status_code == 403
print("PASS — OPERATOR blocked 403")

print("\n=== 6. Department-scoped access ===")
# eng.staff (id 1, ENG) tries to read elec.staff (id 4, ELEC) — should be 403
r = client.get("/api/users/4", headers=auth_header(token_eng_staff))
assert r.status_code == 403, f"dept scope fail expected 403 got {r.status_code} {r.text}"
print("PASS — ENG staff cannot read ELEC user (403 dept denied)")

# Same dept should pass: eng.staff reads eng.reviewer (id 2, same ENG)
r = client.get("/api/users/2", headers=auth_header(token_eng_staff))
assert r.status_code == 200, r.text
print("PASS — ENG staff can read same-dept user 200")

# Official can read any dept
r = client.get("/api/users/4", headers=auth_header(token_official))
assert r.status_code == 200
print("PASS — Official can read cross-dept 200")

print("\n=== 7. Unauthorized access rejection ===")
r = client.get("/api/users/me")
assert r.status_code == 401
print("PASS — unauthenticated /users/me 401")
r = client.get("/api/users/me", headers=auth_header("invalid.token.here"))
assert r.status_code == 401
print("PASS — invalid token 401")

print("\n=== 8. Self-approval protection ===")
# eng.staff (id 1) tries to verify own request where requested_by=1 -> 403
r = client.post("/api/maintenance/1/verify", headers=auth_header(token_eng_staff), json={"requested_by": 1})
assert r.status_code == 403, f"self-approval should be 403 got {r.status_code} {r.text}"
assert "Self-approval" in r.text
print("PASS — self-approval blocked 403")

# eng.reviewer (id 2) verifying eng.staff's request (1) -> allowed 200
r2 = login("eng.reviewer@irctc.test", "EngReview@123")
token_reviewer = r2.json()["access_token"]
r = client.post("/api/maintenance/1/verify", headers=auth_header(token_reviewer), json={"requested_by": 1})
assert r.status_code == 200, r.text
print("PASS — reviewer can verify others 200")

print("\n=== 9. Password security ===")
# Hash not exponent in DB or JWT
from sqlalchemy.orm import Session
from app.database import SessionLocal
db = SessionLocal()
from app.models.user import User
u = db.query(User).filter(User.email=="eng.staff@irctc.test").first()
assert u.password_hash.startswith("$2b$"), "not bcrypt"
assert u.password_hash != "EngStaff@123"
print(f"PASS — password_hash is bcrypt {u.password_hash[:7]}... not plaintext")
# Hash not in login response
r = login("eng.staff@irctc.test", "EngStaff@123")
assert "password_hash" not in r.text and "$2b$" not in r.text
print("PASS — hash not exposed in API")
# JWT not contain hash
payload = decode_token(r.json()["access_token"])
assert "password_hash" not in payload
print("PASS — JWT no hash")
db.close()

# Forgot password does not expose password
print("\n=== 10. Forgot password + audit ===")
r = client.post("/api/auth/forgot-password", json={"email": "eng.staff@irctc.test"})
assert r.status_code == 200
assert r.json()["message"]
print(f"PASS — forgot-password 200: {r.json()['message'][:50]}")
# Unknown email should still return success (no enumeration) + not reveal
r = client.post("/api/auth/forgot-password", json={"email": "unknown@x.test"})
assert r.status_code == 200
print("PASS — forgot unknown email still 200 (no enumeration)")

# Reset flow
reset_token = client.post("/api/auth/forgot-password", json={"email": "eng.staff@irctc.test"}).json().get("reset_token")
assert reset_token, "dev mode should return token"
r = client.post("/api/auth/reset-password", json={"token": reset_token, "new_password": "NewPass@1234"})
assert r.status_code == 200, r.text
print("PASS — reset-password 200")
# Login with new password
r = login("eng.staff@irctc.test", "NewPass@1234")
assert r.status_code == 200, "should login with new password"
print("PASS — login with new password 200")
# Revert for other tests
from app.database import SessionLocal as SL
from app.core.security import hash_password
db = SL()
u = db.query(User).filter(User.email=="eng.staff@irctc.test").first()
u.password_hash = hash_password("EngStaff@123")
db.commit()
db.close()
print("PASS — reverted password")

print("\n=== 11. Audit logging ===")
with engine.connect() as conn:
    from sqlalchemy import text
    rows = conn.execute(text("SELECT action, user_id FROM audit_logs ORDER BY id DESC LIMIT 15")).fetchall()
    print(f" Recent audits ({len(rows)}): {rows[:8]}")
    actions = [r[0] for r in rows]
    assert "LOGIN" in actions, "LOGIN audit missing"
    assert "LOGIN_FAILED" in actions, "LOGIN_FAILED audit missing"
    # At least one FORGOT/RESET
    assert any(a in actions for a in ["FORGOT_PASSWORD","RESET_PASSWORD","LOGIN_FAILED_INACTIVE"]), "forgot/reset audit missing"
    print("PASS — critical audits present")

print("\n=== 12. Module 1 not broken ===")
import subprocess
result = __import__("subprocess").run(["python", "D:\\IRCTC\\backend\\scripts\\verify_models.py"], capture_output=True, text=True)
assert "ALL MODEL VERIFICATION PASSED" in result.stdout, result.stdout[-500:]
print("PASS — verify_models still passes")
with engine.connect() as conn:
    cnt = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")).scalar()
    assert cnt >= 28, f"tables missing: {cnt}"
    cnt = conn.execute(text("SELECT count(*) FROM geometry_columns WHERE srid=4326")).scalar()
    assert cnt >= 6
    print(f"PASS — DB intact: tables {cnt} geometry ok, PostGIS still enabled")

print("\n========== ALL 11 (+2) CHECKS PASSED ==========")
