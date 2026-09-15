"""
Seed 10+ department-role users for Module 2 testing.
Covers every valid mapping + inactive user + extra for dept-scoped tests.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models.department import Department
from app.models.user import User
from app.core.security import hash_password

# Definition: one user per valid department_role + one inactive + one extra ENG staffer for self-approval
USERS = [
    # ENG
    {"name": "A. Kumar", "email": "eng.staff@irctc.test", "password": "EngStaff@123", "dept_code": "ENG", "role": "MAINTENANCE_STAFF"},
    {"name": "B. Sharma", "email": "eng.reviewer@irctc.test", "password": "EngReview@123", "dept_code": "ENG", "role": "ENGINEER_REVIEWER"},
    {"name": "C. Patel", "email": "eng.staff2@irctc.test", "password": "EngStaff2@123", "dept_code": "ENG", "role": "MAINTENANCE_STAFF"},
    # ELEC
    {"name": "D. Singh", "email": "elec.staff@irctc.test", "password": "ElecStaff@123", "dept_code": "ELEC", "role": "MAINTENANCE_STAFF"},
    {"name": "E. Reddy", "email": "elec.reviewer@irctc.test", "password": "ElecReview@123", "dept_code": "ELEC", "role": "ENGINEER_REVIEWER"},
    # SNT
    {"name": "F. Das", "email": "snt.staff@irctc.test", "password": "SntStaff@123", "dept_code": "SNT", "role": "MAINTENANCE_STAFF"},
    {"name": "G. Nair", "email": "snt.reviewer@irctc.test", "password": "SntReview@123", "dept_code": "SNT", "role": "ENGINEER_REVIEWER"},
    # OPS
    {"name": "H. Operator", "email": "ops.operator@irctc.test", "password": "OpsOper@123", "dept_code": "OPS", "role": "OPERATOR"},
    # CONTROL
    {"name": "I. Controller", "email": "control.controller@irctc.test", "password": "Control@123", "dept_code": "CONTROL", "role": "CONTROLLER"},
    # RAILWAY official
    {"name": "J. Official", "email": "railway.official@irctc.test", "password": "Official@123", "dept_code": "RAILWAY", "role": "AUTHORIZED_OFFICIAL"},
    # EMERGENCY
    {"name": "K. Emergency", "email": "emergency.operator@irctc.test", "password": "Emergency@123", "dept_code": "EMERGENCY", "role": "EMERGENCY_OPERATOR"},
    # Inactive user
    {"name": "L. Inactive", "email": "inactive@irctc.test", "password": "Inactive@123", "dept_code": "ENG", "role": "MAINTENANCE_STAFF", "is_active": False},
]


def seed():
    db = SessionLocal()
    try:
        # Resolve dept ids
        depts = {d.code: d.id for d in db.query(Department).all()}
        print(f"Departments: {depts}")
        created = 0
        for u in USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"Skip existing {u['email']}")
                continue
            dept_id = depts.get(u["dept_code"])
            if not dept_id:
                print(f"Missing dept {u['dept_code']}")
                continue
            user = User(
                name=u["name"],
                email=u["email"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
                department_id=dept_id,
                is_active=u.get("is_active", True),
            )
            db.add(user)
            created += 1
        db.commit()
        print(f"Created {created} users")
        # Verify
        total = db.query(User).count()
        print(f"Total users now: {total}")
        for u in db.query(User).limit(15):
            dept = db.query(Department).filter(Department.id == u.department_id).first()
            print(f"  {u.id:2d} {u.email:35s} {u.role:20s} {dept.code:8s} active={u.is_active}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
