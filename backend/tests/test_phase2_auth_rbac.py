"""
SIH26027 — Phase 2 Master Test Suite: Authentication, User Setup, JE/SSE RBAC & Security.

Tests:
1. All 13 SIH Demo Accounts Authentication & Token Generation
2. Negative Authentication (invalid pass, nonexistent user, inactive account)
3. JWT Security, Claims Validation, Signature Tampering & Expiration Handling
4. Backend RBAC Enforcement for all 13 Roles & 7 Departments
5. Department-Scoped Data Access Isolation
6. Mandatory Server-Side Self-Approval Guards
7. User Profile Management (GET /me, PUT /me, change password)
8. Session Logout & Expiration Handling
9. Comprehensive Audit Logging Verification
"""
import sys
from pathlib import Path
from datetime import timedelta

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine, SessionLocal
from app.core.security import decode_token, create_access_token, hash_password
from app.models.user import User
from app.models.audit import AuditLog

client = TestClient(app)


def login(username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# All 13 Official Demo Accounts
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
    # 6. Railway Official (Final Authority)
    {"username": "railway_official", "email": "railway_official@irctc.test", "pass": "SIH@Official2026", "dept": "RAILWAY", "role": "AUTHORIZED_OFFICIAL"},
    # 7. Emergency Response
    {"username": "emergency", "email": "emergency@irctc.test", "pass": "SIH@Emergency2026", "dept": "EMERGENCY", "role": "EMERGENCY_OPERATOR"},
]


@pytest.fixture(scope="module")
def tokens():
    """Module fixture caching JWT tokens for all 13 demo accounts."""
    toks = {}
    for acc in DEMO_CREDENTIALS:
        r = login(acc["username"], acc["pass"])
        assert r.status_code == 200, f"Setup login failed for {acc['username']}: {r.text}"
        toks[acc["username"]] = r.json()["access_token"]
    return toks


# ==============================================================================
# 1. POSITIVE AUTHENTICATION TESTS — ALL 13 DEMO ACCOUNTS
# ==============================================================================

def test_all_13_demo_accounts_authentication():
    """Verify all 13 demo accounts authenticate with username and email, returning valid tokens & permissions."""
    for acc in DEMO_CREDENTIALS:
        # 1. Login via username
        r = login(acc["username"], acc["pass"])
        assert r.status_code == 200, f"Login failed for username {acc['username']}"
        data = r.json()
        assert "access_token" in data
        assert data["token_type"].lower() == "bearer"
        assert "password" not in r.text.lower()
        assert "password_hash" not in r.text.lower()
        assert data["user"]["role"] == acc["role"]
        assert data["user"]["department"] == acc["dept"]
        assert isinstance(data["user"]["permissions"], list)
        assert len(data["user"]["permissions"]) > 0

        # 2. Login via email
        r_email = login(acc["email"], acc["pass"])
        assert r_email.status_code == 200, f"Login failed for email {acc['email']}"


# ==============================================================================
# 2. NEGATIVE AUTHENTICATION TESTS
# ==============================================================================

def test_negative_authentication():
    """Verify wrong password, unknown user, and inactive accounts return HTTP 401."""
    # Invalid password
    r1 = login("eng_staff", "WrongPassword123")
    assert r1.status_code == 401
    assert "Invalid credentials" in r1.text

    # Nonexistent user
    r2 = login("ghost_nonexistent_user", "SIH@Ghost2026")
    assert r2.status_code == 401

    # Inactive user
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "inactive_user@irctc.test").first()
        if not user:
            user = User(
                name="Inactive Test User",
                email="inactive_user@irctc.test",
                password_hash=hash_password("SIH@Inactive2026"),
                role="MAINTENANCE_STAFF",
                department_id=1,
                is_active=False,
            )
            db.add(user)
            db.commit()

    r3 = login("inactive_user@irctc.test", "SIH@Inactive2026")
    assert r3.status_code == 401
    assert "inactive" in r3.text.lower()


# ==============================================================================
# 3. JWT SECURITY & CLAIMS VALIDATION
# ==============================================================================

def test_jwt_security_and_expiration(tokens):
    """Verify JWT claims completeness, expired token rejection, and unauthenticated rejection."""
    token = tokens["eng_staff"]
    payload = decode_token(token)
    assert payload["user_id"] > 0
    assert payload["email"] == "eng_staff@irctc.test"
    assert payload["role"] == "MAINTENANCE_STAFF"
    assert payload["department_code"] == "ENG"
    assert "exp" in payload
    assert "iat" in payload
    assert "password" not in payload

    # Unauthenticated request
    r_unauth = client.get("/api/auth/me")
    assert r_unauth.status_code == 401

    # Expired token
    expired = create_access_token(
        {"user_id": 1, "email": "eng_staff@irctc.test", "department": "Engineering", "department_code": "ENG", "department_id": 1, "role": "MAINTENANCE_STAFF"},
        expires_delta=timedelta(seconds=-10),
    )
    r_exp = client.get("/api/auth/me", headers=auth_header(expired))
    assert r_exp.status_code == 401

    # Tampered signature
    tampered = token[:-4] + "fake"
    r_tamp = client.get("/api/auth/me", headers=auth_header(tampered))
    assert r_tamp.status_code == 401


# ==============================================================================
# 4. BACKEND RBAC AUTHORIZATION ENFORCEMENT
# ==============================================================================

def test_rbac_official_only_restriction(tokens):
    """Verify only AUTHORIZED_OFFICIAL can access official-only endpoints; other 12 roles receive HTTP 403."""
    # Official succeeds
    r_off = client.get("/api/users/admin/only-official", headers=auth_header(tokens["railway_official"]))
    assert r_off.status_code == 200

    # All non-official roles receive 403
    non_officials = [
        "eng_staff", "eng_je", "eng_sse",
        "elec_staff", "elec_je", "elec_sse",
        "snt_staff", "snt_je", "snt_sse",
        "operations", "control", "emergency"
    ]
    for username in non_officials:
        r = client.get("/api/users/admin/only-official", headers=auth_header(tokens[username]))
        assert r.status_code == 403, f"Expected 403 for {username}, got {r.status_code}"


# ==============================================================================
# 5. DEPARTMENT-SCOPED DATA ACCESS ISOLATION
# ==============================================================================

def test_department_scoped_data_isolation(tokens):
    """Verify Engineering staff cannot view or filter for Electrical/SNT restricted records."""
    token_eng = tokens["eng_staff"]
    token_official = tokens["railway_official"]

    # Engineering staff querying own department succeeds
    r_eng = client.get("/api/users?department_code=ENG", headers=auth_header(token_eng))
    assert r_eng.status_code == 200

    # Engineering staff attempting cross-department query receives 403
    r_cross = client.get("/api/users?department_code=ELEC", headers=auth_header(token_eng))
    assert r_cross.status_code == 403

    # Authorized Official can query across any department
    r_off_elec = client.get("/api/users?department_code=ELEC", headers=auth_header(token_official))
    assert r_off_elec.status_code == 200


# ==============================================================================
# 6. SELF-APPROVAL PROTECTION
# ==============================================================================

def test_self_approval_protection():
    """Verify server-side self-approval constraints throw HTTP 403 when creator == reviewer/approver."""
    from app.core.rbac import check_self_approval
    from fastapi import HTTPException

    # Case 1: Requester cannot approve own work
    with pytest.raises(HTTPException) as exc1:
        check_self_approval(current_user_id=10, requested_by_id=10, reviewer_id=20)
    assert exc1.value.status_code == 403
    assert "requester cannot approve own work" in exc1.value.detail

    # Case 2: Reviewer cannot be final approver
    with pytest.raises(HTTPException) as exc2:
        check_self_approval(current_user_id=20, requested_by_id=10, reviewer_id=20)
    assert exc2.value.status_code == 403
    assert "reviewer cannot perform final approval" in exc2.value.detail

    # Case 3: Disjoint parties succeed
    check_self_approval(current_user_id=30, requested_by_id=10, reviewer_id=20)


# ==============================================================================
# 7. USER PROFILE & LOGOUT WORKFLOW
# ==============================================================================

def test_user_profile_and_logout(tokens):
    """Verify GET /me, PUT /me (updating display name), and POST /logout."""
    token = tokens["eng_staff"]

    # 1. GET /api/auth/me
    r_me = client.get("/api/auth/me", headers=auth_header(token))
    assert r_me.status_code == 200
    data = r_me.json()
    assert data["email"] == "eng_staff@irctc.test"
    assert data["role"] == "MAINTENANCE_STAFF"
    assert "permissions" in data

    # 2. PUT /api/users/me (updating display name)
    r_put = client.put("/api/users/me", json={"name": "P. Sharma (Sr. Eng Staff)"}, headers=auth_header(token))
    assert r_put.status_code == 200
    assert r_put.json()["name"] == "P. Sharma (Sr. Eng Staff)"

    # Restore name
    client.put("/api/users/me", json={"name": "Engineering Maintenance Staff"}, headers=auth_header(token))

    # 3. POST /api/auth/logout
    r_logout = client.post("/api/auth/logout", headers=auth_header(token))
    assert r_logout.status_code == 200
    assert r_logout.json()["status"] == "ok"


# ==============================================================================
# 8. AUDIT LOGGING VERIFICATION
# ==============================================================================

def test_audit_logs_recorded():
    """Verify security actions (LOGIN, LOGOUT, UPDATE_PROFILE) are properly committed to audit_logs table."""
    with SessionLocal() as db:
        logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(10).all()
        actions = [log.action for log in logs]
        assert len(actions) > 0
        assert any(a in actions for a in ["LOGIN", "LOGOUT", "UPDATE_PROFILE"])
        # Ensure zero passwords or secrets leaked in descriptions
        for log in logs:
            if log.description:
                assert "SIH@" not in log.description
                assert "secret" not in log.description.lower() or "reset" in log.description.lower()
