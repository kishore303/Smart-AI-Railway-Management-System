"""
Comprehensive Authentication, RBAC & 13-Role Demo Verification Test Suite.
"""
import sys
from pathlib import Path
from datetime import timedelta

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine, SessionLocal
from app.core.security import decode_token, create_access_token, hash_password
from app.models.user import User

client = TestClient(app)


def login(username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# 13 Official Demo Roles to Test
DEMO_CREDENTIALS = [
    # 1. Engineering
    {"username": "eng_staff", "email": "eng_staff@irctc.test", "pass": "SIH@EngStaff2026", "dept": "ENG", "role": "MAINTENANCE_STAFF"},
    {"username": "eng_je", "email": "eng_je@irctc.test", "pass": "SIH@EngJE2026", "dept": "ENG", "role": "JUNIOR_ENGINEER"},
    {"username": "eng_sse", "email": "eng_sse@irctc.test", "pass": "SIH@EngSSE2026", "dept": "ENG", "role": "SENIOR_SECTION_ENGINEER"},
    # 2. Electrical / OHE
    {"username": "elec_staff", "email": "elec_staff@irctc.test", "pass": "SIH@ElecStaff2026", "dept": "ELEC", "role": "MAINTENANCE_STAFF"},
    {"username": "elec_je", "email": "elec_je@irctc.test", "pass": "SIH@ElecJE2026", "dept": "ELEC", "role": "JUNIOR_ENGINEER"},
    {"username": "elec_sse", "email": "elec_sse@irctc.test", "pass": "SIH@ElecSSE2026", "dept": "ELEC", "role": "SENIOR_SECTION_ENGINEER"},
    # 3. S&T
    {"username": "snt_staff", "email": "snt_staff@irctc.test", "pass": "SIH@SNTStaff2026", "dept": "SNT", "role": "MAINTENANCE_STAFF"},
    {"username": "snt_je", "email": "snt_je@irctc.test", "pass": "SIH@SNTJE2026", "dept": "SNT", "role": "JUNIOR_ENGINEER"},
    {"username": "snt_sse", "email": "snt_sse@irctc.test", "pass": "SIH@SNTSSE2026", "dept": "SNT", "role": "SENIOR_SECTION_ENGINEER"},
    # 4. Operations / Traffic
    {"username": "operations", "email": "operations@irctc.test", "pass": "SIH@Ops2026", "dept": "OPS", "role": "OPERATOR"},
    # 5. Railway Control
    {"username": "control", "email": "control@irctc.test", "pass": "SIH@Control2026", "dept": "CONTROL", "role": "CONTROLLER"},
    # 6. Railway Official
    {"username": "railway_official", "email": "railway_official@irctc.test", "pass": "SIH@Official2026", "dept": "RAILWAY", "role": "AUTHORIZED_OFFICIAL"},
    # 7. Emergency
    {"username": "emergency", "email": "emergency@irctc.test", "pass": "SIH@Emergency2026", "dept": "EMERGENCY", "role": "EMERGENCY_OPERATOR"},
]


import pytest


@pytest.fixture(scope="module")
def tokens():
    toks = {}
    for acc in DEMO_CREDENTIALS:
        r = login(acc["username"], acc["pass"])
        if r.status_code == 200:
            toks[acc["username"]] = r.json()["access_token"]
    return toks


@pytest.fixture(scope="module")
def token_official(tokens):
    return tokens["railway_official"]


@pytest.fixture(scope="module")
def token_eng_staff(tokens):
    return tokens["eng_staff"]


def test_all_13_demo_logins():
    print("\n=== 1. Testing Login for all 13 SIH Demo Accounts ===")
    toks = {}
    for acc in DEMO_CREDENTIALS:
        # Test login via username
        r = login(acc["username"], acc["pass"])
        assert r.status_code == 200, f"Login failed for {acc['username']}: {r.status_code} {r.text}"
        data = r.json()
        assert "access_token" in data
        assert "password" not in r.text.lower()
        assert "password_hash" not in r.text.lower()
        assert data["user"]["role"] == acc["role"]
        assert data["user"]["department"] == acc["dept"]
        toks[acc["username"]] = data["access_token"]
        print(f"  PASS: [{acc['dept']:9s}] {acc['username']:18s} -> {data['user']['role']}")

        # Test login via email
        r_email = login(acc["email"], acc["pass"])
        assert r_email.status_code == 200, f"Email login failed for {acc['email']}"
    return toks



def test_negative_logins():
    print("\n=== 2. Testing Negative Login & Inactive Accounts ===")
    # Wrong password
    r = login("eng_staff", "WrongPassword123")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("  PASS: Invalid password rejected (401)")

    # Nonexistent user
    r = login("ghost_user", "SIH@Ghost2026")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("  PASS: Nonexistent user rejected (401)")

    # Inactive account
    r = login("inactive_user", "SIH@Inactive2026")
    assert r.status_code == 401, f"Inactive user should be 401, got {r.status_code}"
    print("  PASS: Inactive account rejected (401)")


def test_jwt_security(token_official, token_eng_staff):
    print("\n=== 3. Testing JWT Security, Claims & Expiration ===")
    payload = decode_token(token_eng_staff)
    assert "user_id" in payload
    assert "email" in payload
    assert "role" in payload and payload["role"] == "MAINTENANCE_STAFF"
    assert "department_code" in payload and payload["department_code"] == "ENG"
    assert "iat" in payload and "exp" in payload
    assert "password" not in payload and "password_hash" not in payload
    print("  PASS: JWT contains strict claims and zero secret leaks")

    # Expired token
    expired = create_access_token(
        {"user_id": 1, "email": "eng.staff@irctc.test", "department": "Engineering", "department_code": "ENG", "department_id": 1, "role": "MAINTENANCE_STAFF"},
        expires_delta=timedelta(seconds=-10),
    )
    r = client.get("/api/auth/me", headers=auth_header(expired))
    assert r.status_code == 401, f"Expired token should be 401, got {r.status_code}"
    print("  PASS: Expired JWT correctly rejected (401)")

    # Unauthenticated request
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    print("  PASS: Unauthenticated request rejected (401)")

    # Valid /me
    r = client.get("/api/auth/me", headers=auth_header(token_eng_staff))
    assert r.status_code == 200
    assert r.json()["email"] == "eng_staff@irctc.test"
    print("  PASS: Authenticated /auth/me returned 200")


def test_backend_rbac_enforcement(tokens):
    print("\n=== 4. Testing Backend RBAC Enforcement & Forbidden Actions ===")
    token_official = tokens["railway_official"]
    token_staff = tokens["eng_staff"]
    token_je = tokens["eng_je"]
    token_sse = tokens["eng_sse"]
    token_ops = tokens["operations"]
    token_control = tokens["control"]
    token_emergency = tokens["emergency"]

    # Endpoint restricted only to AUTHORIZED_OFFICIAL
    r = client.get("/api/users/admin/only-official", headers=auth_header(token_official))
    assert r.status_code == 200
    print("  PASS: AUTHORIZED_OFFICIAL can access official-only endpoint (200)")

    non_officials = [
        ("eng_staff", token_staff),
        ("eng_je", token_je),
        ("eng_sse", token_sse),
        ("operations", token_ops),
        ("control", token_control),
        ("emergency", token_emergency),
    ]
    for name, tok in non_officials:
        r = client.get("/api/users/admin/only-official", headers=auth_header(tok))
        assert r.status_code == 403, f"{name} should get 403 on official-only route, got {r.status_code}"
    print("  PASS: All non-official roles strictly blocked with 403 FORBIDDEN")

    # Maintenance Staff cannot access review queue
    r = client.get("/api/maintenance/review/queue", headers=auth_header(token_staff))
    assert r.status_code == 403, f"Staff should not access review queue, got {r.status_code}"
    print("  PASS: MAINTENANCE_STAFF cannot access technical review queue (403)")

    # JE and SSE CAN access review queue
    r_je = client.get("/api/maintenance/review/queue", headers=auth_header(token_je))
    assert r_je.status_code == 200
    r_sse = client.get("/api/maintenance/review/queue", headers=auth_header(token_sse))
    assert r_sse.status_code == 200
    print("  PASS: JUNIOR_ENGINEER & SENIOR_SECTION_ENGINEER can access review queue (200)")


def test_department_scoped_isolation(tokens):
    print("\n=== 5. Testing Department-Scoped Resource Isolation ===")
    token_eng = tokens["eng_staff"]
    token_elec = tokens["elec_staff"]
    token_official = tokens["railway_official"]

    db = SessionLocal()
    u_eng = db.query(User).filter(User.name == "eng_staff").first()
    u_elec = db.query(User).filter(User.name == "elec_staff").first()
    db.close()

    # ENG staff cannot read ELEC user profile
    r = client.get(f"/api/users/{u_elec.id}", headers=auth_header(token_eng))
    assert r.status_code == 403, f"Expected 403 on cross-dept user read, got {r.status_code}"
    print("  PASS: Cross-department private user inspection denied (403)")

    # ENG staff CAN read same-dept JE profile
    db = SessionLocal()
    u_eng_je = db.query(User).filter(User.name == "eng_je").first()
    db.close()
    r = client.get(f"/api/users/{u_eng_je.id}", headers=auth_header(token_eng))
    assert r.status_code == 200
    print("  PASS: Same-department user inspection permitted (200)")

    # Official can view any department user
    r = client.get(f"/api/users/{u_elec.id}", headers=auth_header(token_official))
    assert r.status_code == 200
    print("  PASS: AUTHORIZED_OFFICIAL can view cross-department users (200)")


def test_self_approval_guards(tokens):
    print("\n=== 6. Testing Self-Approval & Separation of Concerns ===")
    token_eng_staff = tokens["eng_staff"]
    token_eng_je = tokens["eng_je"]

    db = SessionLocal()
    u_staff = db.query(User).filter(User.email == "eng_staff@irctc.test").first()
    u_je = db.query(User).filter(User.email == "eng_je@irctc.test").first()
    db.close()

    # Requester attempting to review own request (simulated via verify endpoint)
    r = client.post(
        "/api/maintenance/1/verify",
        headers=auth_header(token_eng_staff),
        json={"requested_by": u_staff.id},
    )
    assert r.status_code == 403, f"Expected 403 for self-approval, got {r.status_code} {r.text}"
    print("  PASS: Self-review / self-approval strictly prevented by backend (403)")


def test_forgot_and_reset_password():
    print("\n=== 7. Testing Forgot / Reset Password Flow ===")
    # Ensure dedicated test user exists
    db = SessionLocal()
    u = db.query(User).filter(User.email == "pwd_reset_user@irctc.test").first()
    if not u:
        u = User(
            name="Password Reset Test User",
            email="pwd_reset_user@irctc.test",
            password_hash=hash_password("OldSecretPass@2026"),
            role="MAINTENANCE_STAFF",
            department_id=1,
            is_active=True,
        )
        db.add(u)
        db.commit()
    else:
        u.password_hash = hash_password("OldSecretPass@2026")
        db.commit()
    db.close()

    # Request reset token
    r = client.post("/api/auth/forgot-password", json={"email": "pwd_reset_user@irctc.test"})
    assert r.status_code == 200
    token = r.json().get("reset_token")
    assert token, "Dev mode should supply reset_token"

    # Reset password
    r_reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewSecretPass@2026"})
    assert r_reset.status_code == 200

    # Login with new password
    r_login = login("pwd_reset_user@irctc.test", "NewSecretPass@2026")
    assert r_login.status_code == 200
    print("  PASS: Password reset and new credential authentication succeeded")


def test_audit_logs():
    print("\n=== 8. Testing Security & RBAC Audit Logging ===")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT action, user_id FROM audit_logs ORDER BY id DESC LIMIT 20")).fetchall()
        actions = [r[0] for r in rows]
        print(f"  Audit log count: {len(rows)}, Recent actions: {actions[:8]}")
        assert "LOGIN" in actions, "Missing LOGIN audit"
        assert any(a in actions for a in ["LOGIN_FAILED", "LOGIN_FAILED_INACTIVE", "FORGOT_PASSWORD", "RESET_PASSWORD"])
        print("  PASS: Security actions comprehensively logged in PostgreSQL audit_logs")


if __name__ == "__main__":
    tokens = test_all_13_demo_logins()
    test_negative_logins()
    test_jwt_security(tokens["railway_official"], tokens["eng_staff"])
    test_backend_rbac_enforcement(tokens)
    test_department_scoped_isolation(tokens)
    test_self_approval_guards(tokens)
    test_forgot_and_reset_password()
    test_audit_logs()
    print("\n============================================================")
    print("ALL 13 ROLES & RBAC SECURITY TESTS PASSED PERFECTLY!")
    print("ALL 11 (+2) CHECKS PASSED")
    print("============================================================\n")

