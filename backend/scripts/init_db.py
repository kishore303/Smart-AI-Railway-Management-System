"""
Module 1 — Database initialization.

Creates database sih26027 if not exists, enables PostGIS,
and executes authoritative_schema.sql.

Usage:
  python -m scripts.init_db
  or: python backend/scripts/init_db.py
"""
import os
import sys
from pathlib import Path

# Ensure backend is on path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")

# Parse DATABASE_URL to extract parts
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/sih26027")

# Extract for psycopg2 direct connections (without +psycopg2 prefix)
# Format: postgresql+psycopg2://user:pass@host:port/dbname
import re

m = re.match(r"postgresql\+psycopg2://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", DATABASE_URL)
if not m:
    m = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", DATABASE_URL)
if m:
    DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME = m.groups()
else:
    DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME = ("postgres", "postgres", "localhost", "5432", "sih26027")

SQL_FILE = backend_dir / "sql" / "authoritative_schema.sql"


def get_admin_conn():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def ensure_database():
    conn = get_admin_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
    exists = cur.fetchone() is not None
    if not exists:
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"Created database {DB_NAME}")
    else:
        print(f"Database {DB_NAME} already exists")
    cur.close()
    conn.close()


def enable_postgis():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute("SELECT postgis_full_version();")
    ver = cur.fetchone()
    print(f"PostGIS: {ver[0][:120] if ver else 'unknown'}")
    cur.close()
    conn.close()


def apply_schema(drop_first: bool = True):
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    if drop_first:
        print("Dropping existing schema objects (CASCADE)...")
        # Drop view first, then tables, then types
        cur.execute(
            """
            DROP VIEW IF EXISTS section_traffic_stats CASCADE;
            DROP TABLE IF EXISTS
                audit_logs, simulations, emergency_responses, incidents,
                notifications, block_resource_allocations, block_affected_trains,
                optimized_block_sources, block_candidates, optimized_blocks,
                block_integration_requests, block_requests, ml_model_registry,
                maintenance_predictions, maintenance_requests, train_schedules, trains,
                resources, weather_readings, asset_failure_history, asset_sensor_readings,
                assets, tracks, railway_sections, stations, users, department_roles, departments
                CASCADE;
            DROP TYPE IF EXISTS notification_type, emergency_response_status, incident_response_status,
                incident_type, integration_final_status, integration_response,
                optimized_block_status, block_request_status, maintenance_request_status,
                notification_priority, severity_level, user_role CASCADE;
            DROP FUNCTION IF EXISTS set_updated_at() CASCADE;
            """
        )
        print("Dropped old objects")

    sql = SQL_FILE.read_text(encoding="utf-8")
    print(f"Applying {SQL_FILE} ({len(sql)} bytes)...")
    cur.execute(sql)
    print("Schema applied successfully")

    # Verify
    cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
    tbl_count = cur.fetchone()[0]
    print(f"Public tables: {tbl_count}")

    cur.execute("SELECT department_code FROM (VALUES ('ENG'),('ELEC'),('SNT'),('OPS'),('CONTROL'),('RAILWAY'),('EMERGENCY')) t(department_code) LIMIT 1")
    cur.execute("SELECT code FROM departments ORDER BY id")
    depts = [r[0] for r in cur.fetchall()]
    print(f"Departments: {depts}")

    cur.execute("SELECT role FROM department_roles ORDER BY department_id, role")
    roles = cur.fetchall()
    print(f"DepartmentRoles rows: {len(roles)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    print(f"Using DB: {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}")
    print(f"SQL file: {SQL_FILE} exists={SQL_FILE.exists()}")
    ensure_database()
    enable_postgis()
    apply_schema(drop_first=True)
    print("Done — Module 1 DB ready")
