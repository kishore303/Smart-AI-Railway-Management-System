"""
Seed SIH Demo Users for all 13 department-role combinations per master specification,
plus compatibility users for existing test suites.
"""
import os
import re
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")

from app.database import SessionLocal
from app.models.department import Department
from app.models.user import User
from app.core.security import hash_password

# 13 Official Demo Users for SIH Jury Access + Legacy Compatibility Users
ALL_USERS = [
    # =========================================================================
    # 13 OFFICIAL SIH DEMO ACCOUNTS (FOR SIH JURY ACCESS)
    # =========================================================================
    # --- 1. Engineering ---
    {
        "name": "eng_staff",
        "email": "eng_staff@irctc.test",
        "dept_code": "ENG",
        "role": "MAINTENANCE_STAFF",
    },
    {
        "name": "eng_je",
        "email": "eng_je@irctc.test",
        "dept_code": "ENG",
        "role": "JUNIOR_ENGINEER",
    },
    {
        "name": "eng_sse",
        "email": "eng_sse@irctc.test",
        "dept_code": "ENG",
        "role": "SENIOR_SECTION_ENGINEER",
    },

    # --- 2. Electrical / OHE ---
    {
        "name": "elec_staff",
        "email": "elec_staff@irctc.test",
        "dept_code": "ELEC",
        "role": "MAINTENANCE_STAFF",
    },
    {
        "name": "elec_je",
        "email": "elec_je@irctc.test",
        "dept_code": "ELEC",
        "role": "JUNIOR_ENGINEER",
    },
    {
        "name": "elec_sse",
        "email": "elec_sse@irctc.test",
        "dept_code": "ELEC",
        "role": "SENIOR_SECTION_ENGINEER",
    },

    # --- 3. S&T (Signal & Telecom) ---
    {
        "name": "snt_staff",
        "email": "snt_staff@irctc.test",
        "dept_code": "SNT",
        "role": "MAINTENANCE_STAFF",
    },
    {
        "name": "snt_je",
        "email": "snt_je@irctc.test",
        "dept_code": "SNT",
        "role": "JUNIOR_ENGINEER",
    },
    {
        "name": "snt_sse",
        "email": "snt_sse@irctc.test",
        "dept_code": "SNT",
        "role": "SENIOR_SECTION_ENGINEER",
    },

    # --- 4. Operations / Traffic ---
    {
        "name": "operations",
        "email": "operations@irctc.test",
        "dept_code": "OPS",
        "role": "OPERATOR",
    },

    # --- 5. Railway Control ---
    {
        "name": "control",
        "email": "control@irctc.test",
        "dept_code": "CONTROL",
        "role": "CONTROLLER",
    },

    # --- 6. Railway Official ---
    {
        "name": "railway_official",
        "email": "railway_official@irctc.test",
        "dept_code": "RAILWAY",
        "role": "AUTHORIZED_OFFICIAL",
    },

    # --- 7. Emergency ---
    {
        "name": "emergency",
        "email": "emergency@irctc.test",
        "dept_code": "EMERGENCY",
        "role": "EMERGENCY_OPERATOR",
    },

    # =========================================================================
    # COMPATIBILITY & TEST USERS (FOR EXISTING AUTOMATED TEST SCRIPTS)
    # =========================================================================
    {"name": "A. Kumar", "email": "eng.staff@irctc.test", "dept_code": "ENG", "role": "MAINTENANCE_STAFF"},
    {"name": "B. Sharma", "email": "eng.reviewer@irctc.test", "dept_code": "ENG", "role": "SENIOR_SECTION_ENGINEER"},
    {"name": "C. Patel", "email": "eng.staff2@irctc.test", "dept_code": "ENG", "role": "MAINTENANCE_STAFF"},
    {"name": "D. Singh", "email": "elec.staff@irctc.test", "dept_code": "ELEC", "role": "MAINTENANCE_STAFF"},
    {"name": "E. Reddy", "email": "elec.reviewer@irctc.test", "dept_code": "ELEC", "role": "SENIOR_SECTION_ENGINEER"},
    {"name": "F. Das", "email": "snt.staff@irctc.test", "dept_code": "SNT", "role": "MAINTENANCE_STAFF"},
    {"name": "G. Nair", "email": "snt.reviewer@irctc.test", "dept_code": "SNT", "role": "SENIOR_SECTION_ENGINEER"},
    {"name": "H. Operator", "email": "ops.operator@irctc.test", "dept_code": "OPS", "role": "OPERATOR"},
    {"name": "I. Controller", "email": "control.controller@irctc.test", "dept_code": "CONTROL", "role": "CONTROLLER"},
    {"name": "J. Official", "email": "railway.official@irctc.test", "dept_code": "RAILWAY", "role": "AUTHORIZED_OFFICIAL"},
    {"name": "K. Emergency", "email": "emergency.operator@irctc.test", "dept_code": "EMERGENCY", "role": "EMERGENCY_OPERATOR"},
    {"name": "L. Inactive", "email": "inactive@irctc.test", "dept_code": "ENG", "role": "MAINTENANCE_STAFF", "is_active": False},
]


def _password_environment_name(user_name: str) -> str:
    key = re.sub(r"[^A-Z0-9]+", "_", user_name.upper()).strip("_")
    return f"SIH_SEED_PASSWORD_{key}"


def seed():
    passwords = {}
    missing_passwords = []
    for user in ALL_USERS:
        env_name = _password_environment_name(user["name"])
        password = os.environ.get(env_name)
        if not password:
            missing_passwords.append(env_name)
        else:
            passwords[user["name"]] = password
    if missing_passwords:
        raise RuntimeError(
            "Set local seed password variables before seeding: "
            + ", ".join(missing_passwords)
        )

    db = SessionLocal()
    try:
        depts = {d.code: d.id for d in db.query(Department).all()}
        print(f"Loaded Departments: {depts}")
        created = 0
        updated = 0

        for u in ALL_USERS:
            dept_id = depts.get(u["dept_code"])
            if not dept_id:
                print(f"Missing dept {u['dept_code']}")
                continue

            existing = db.query(User).filter(
                (User.email == u["email"]) | (User.name == u["name"])
            ).first()

            if existing:
                existing.name = u["name"]
                existing.email = u["email"]
                existing.password_hash = hash_password(passwords[u["name"]])
                existing.role = u["role"]
                existing.department_id = dept_id
                existing.is_active = u.get("is_active", True)
                updated += 1
            else:
                user = User(
                    name=u["name"],
                    email=u["email"],
                    password_hash=hash_password(passwords[u["name"]]),
                    role=u["role"],
                    department_id=dept_id,
                    is_active=u.get("is_active", True),
                )
                db.add(user)
                created += 1

        db.commit()
        print(f"Seed complete: {created} created, {updated} updated.")
        total = db.query(User).count()
        print(f"Total Users in DB: {total}")
        for u in db.query(User).order_by(User.id).all():
            dept = db.query(Department).filter(Department.id == u.department_id).first()
            dept_code = dept.code if dept else "N/A"
            print(f"  [{u.id:2d}] {u.name:18s} | {u.email:32s} | {u.role:24s} | {dept_code:6s} | active={u.is_active}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
