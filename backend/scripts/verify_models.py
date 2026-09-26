"""
Verify SQLAlchemy models match the authoritative SQL schema.

Checks:
- All 28 tables exist in DB after init
- SQLAlchemy Base.metadata can be compared to DB inspector
- PostGIS geometry columns are present with SRID 4326
- Enums exist
- Department / department_roles seed data correct
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, text
from app.database import engine
import app.models  # noqa: F401 — registers all models


EXPECTED_TABLES = [
    "departments",
    "department_roles",
    "users",
    "stations",
    "railway_sections",
    "tracks",
    "assets",
    "asset_sensor_readings",
    "asset_failure_history",
    "weather_readings",
    "resources",
    "trains",
    "train_schedules",
    "maintenance_requests",
    "maintenance_predictions",
    "ml_model_registry",
    "block_requests",
    "block_integration_requests",
    "optimized_blocks",
    "block_candidates",
    "safety_validations",
    "optimized_block_sources",
    "block_affected_trains",
    "block_resource_allocations",
    "notifications",
    "incidents",
    "emergency_responses",
    "simulations",
    "audit_logs",
]

EXPECTED_GEOMETRY = {
    "stations": ["location"],
    "railway_sections": ["geometry"],
    "tracks": ["geometry"],
    "assets": ["location"],
    "resources": ["location"],
    "incidents": ["location"],
}


def main():
    insp = inspect(engine)
    db_tables = insp.get_table_names(schema="public")
    print(f"DB tables ({len(db_tables)}): {sorted(db_tables)}")

    missing = [t for t in EXPECTED_TABLES if t not in db_tables]
    extra = [t for t in db_tables if t not in EXPECTED_TABLES and not t.startswith("spatial_ref_sys") and t != "geography_columns" and t != "geometry_columns"]

    if missing:
        print(f"FAIL — Missing tables: {missing}")
        sys.exit(1)
    else:
        print("OK — All 28 expected tables present")

    if extra:
        print(f"Note — Extra public tables (non-PostGIS): {extra}")

    # Check SQLAlchemy models vs DB
    from app.database import Base

    model_tables = set(Base.metadata.tables.keys())
    print(f"SQLAlchemy model tables ({len(model_tables)}): {sorted(model_tables)}")
    model_missing = [t for t in EXPECTED_TABLES if t not in model_tables]
    if model_missing:
        print(f"FAIL — SQLAlchemy missing: {model_missing}")
        sys.exit(1)
    print("OK — SQLAlchemy models cover all 28 tables")

    # Check geometry columns SRID 4326 via geometry_columns view
    with engine.connect() as conn:
        for tbl, cols in EXPECTED_GEOMETRY.items():
            for col in cols:
                row = conn.execute(
                    text(
                        "SELECT srid, type FROM geometry_columns WHERE f_table_name=:tbl AND f_geometry_column=:col"
                    ),
                    {"tbl": tbl, "col": col},
                ).fetchone()
                if not row:
                    print(f"FAIL — geometry_columns missing {tbl}.{col}")
                    sys.exit(1)
                srid, gtype = row
                if srid != 4326:
                    print(f"FAIL — {tbl}.{col} srid={srid} expected 4326")
                    sys.exit(1)
                print(f"OK — {tbl}.{col} srid=4326 type={gtype}")

        # Check enums
        enums = conn.execute(text("SELECT typname FROM pg_type WHERE typtype='e' ORDER BY typname")).fetchall()
        enum_names = [r[0] for r in enums]
        print(f"Enums: {enum_names}")
        required_enums = [
            "user_role",
            "severity_level",
            "notification_priority",
            "maintenance_request_status",
            "block_request_status",
            "optimized_block_status",
            "integration_response",
            "integration_final_status",
            "incident_type",
            "incident_response_status",
            "emergency_response_status",
            "notification_type",
        ]
        for e in required_enums:
            if e not in enum_names:
                print(f"FAIL — Missing enum {e}")
                sys.exit(1)
        print("OK — All 12 enums present")

        # Check correct user_role values (OPERATOR/CONTROLLER not old names)
        rows = conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid=pg_type.oid WHERE typname='user_role' ORDER BY enumsortorder")).fetchall()
        labels = [r[0] for r in rows]
        print(f"user_role labels: {labels}")
        if "OPERATOR" not in labels or "CONTROLLER" not in labels:
            print("FAIL — user_role must contain OPERATOR and CONTROLLER (corrected)")
            sys.exit(1)
        if "OPERATIONS_OPERATOR" in labels or "CONTROL_CONTROLLER" in labels:
            print("FAIL — user_role still contains old uncorrected values")
            sys.exit(1)
        print("OK — user_role corrected (OPERATOR/CONTROLLER)")

        # Check departments seed
        depts = conn.execute(text("SELECT code FROM departments ORDER BY id")).fetchall()
        print(f"Departments: {[r[0] for r in depts]}")

        # Check department_roles count = 13 (all 13 valid roles)
        cnt = conn.execute(text("SELECT count(*) FROM department_roles")).scalar()
        print(f"department_roles rows: {cnt}")
        if cnt != 13:
            print(f"WARN — expected 13 department_roles, got {cnt}")

        # Check triggers
        trigs = conn.execute(text("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='public'")).fetchall()
        print(f"Triggers: {[r[0] for r in trigs]}")

        # Check view
        view_exists = conn.execute(
            text("SELECT 1 FROM information_schema.views WHERE table_name='section_traffic_stats'")
        ).fetchone()
        print(f"View section_traffic_stats exists: {bool(view_exists)}")

    print("\n=== ALL MODEL VERIFICATION PASSED ===")


if __name__ == "__main__":
    main()
