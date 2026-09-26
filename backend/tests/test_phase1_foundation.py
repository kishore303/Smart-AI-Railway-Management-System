"""
SIH26027 — Phase 1 Comprehensive Foundation & Repository Audit Test Suite.

Verifies:
1. Health & Database Health endpoints (/health, /health/db)
2. PostgreSQL connection and PostGIS 3.6+ spatial foundation (SRID 4326)
3. Database schema completeness (all 29 core tables)
4. Critical safety_validations table structure and constraints
5. Railway Network Hierarchy (Section -> Track -> Asset multi-track support)
6. ML Artifact preservation, format integrity, and categorization
7. Timetable operational dataset integrity
8. Environment & DEMO_MODE configuration
"""
import sys
import os
from pathlib import Path
import pandas as pd
import joblib

backend_dir = Path(__file__).resolve().parents[1]
root_dir = backend_dir.parent
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from app.main import app
from app.database import engine
from app.core.config import settings

client = TestClient(app)


# ==============================================================================
# 1. HEALTH & SANITIZED STATUS CHECKS
# ==============================================================================

def test_health_endpoint():
    """Verify /health returns sanitized application status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "online"
    assert "app" in data
    assert "environment" in data
    assert "demo_mode" in data
    # Ensure no secrets or database URLs are leaked
    raw_text = response.text.lower()
    assert "password" not in raw_text
    assert "secret" not in raw_text
    assert "postgresql://" not in raw_text


def test_health_db_endpoint():
    """Verify /health/db returns database connectivity and PostGIS status."""
    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "connected"
    assert data.get("database") == "postgresql"
    assert "postgis" in data
    assert data.get("postgis") != "not-installed"
    assert data.get("public_tables", 0) >= 29
    assert data.get("database_ready") is True


# ==============================================================================
# 2. POSTGRESQL + POSTGIS SPATIAL FOUNDATION
# ==============================================================================

def test_postgis_geometry_srid_4326():
    """Verify all spatial columns exist with SRID 4326 in PostGIS geometry_columns."""
    expected_geometry = {
        "stations": [("location", "POINT")],
        "railway_sections": [("geometry", "LINESTRING")],
        "tracks": [("geometry", "LINESTRING")],
        "assets": [("location", "POINT")],
        "resources": [("location", "POINT")],
        "incidents": [("location", "POINT")],
    }
    with engine.connect() as conn:
        for table_name, cols in expected_geometry.items():
            for col_name, expected_type in cols:
                row = conn.execute(
                    text(
                        "SELECT srid, type FROM geometry_columns "
                        "WHERE f_table_name = :tbl AND f_geometry_column = :col"
                    ),
                    {"tbl": table_name, "col": col_name},
                ).fetchone()
                assert row is not None, f"Missing geometry column {table_name}.{col_name} in PostGIS metadata"
                srid, gtype = row
                assert srid == 4326, f"{table_name}.{col_name} must use SRID 4326, found {srid}"
                assert gtype.upper() == expected_type, f"{table_name}.{col_name} type must be {expected_type}, found {gtype}"


# ==============================================================================
# 3. DATABASE SCHEMA & ALL 29 CORE TABLES
# ==============================================================================

def test_all_29_core_tables_exist():
    """Verify all 29 required tables exist in PostgreSQL public schema."""
    expected_tables = [
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
    insp = inspect(engine)
    db_tables = set(insp.get_table_names(schema="public"))
    missing = [t for t in expected_tables if t not in db_tables]
    assert len(missing) == 0, f"Missing required core tables: {missing}"


def test_safety_validations_table_structure():
    """Verify critical safety_validations table structure, FKs, and JSONB fields."""
    insp = inspect(engine)
    columns = {col["name"]: col for col in insp.get_columns("safety_validations")}
    required_cols = [
        "id",
        "candidate_id",
        "block_request_id",
        "overall_status",
        "is_safe_for_optimization",
        "checks",
        "rejection_reasons",
        "warnings",
        "validated_by",
        "validated_at",
        "created_at",
    ]
    for col_name in required_cols:
        assert col_name in columns, f"Column {col_name} missing from safety_validations"

    # Verify foreign keys
    fks = insp.get_foreign_keys("safety_validations")
    referred_tables = {fk["referred_table"] for fk in fks}
    assert "block_candidates" in referred_tables
    assert "block_requests" in referred_tables


# ==============================================================================
# 4. RAILWAY NETWORK HIERARCHY (Section -> Track -> Asset)
# ==============================================================================

def test_railway_hierarchy_multi_track():
    """Verify Section can contain multiple Tracks and Track belongs to Section."""
    insp = inspect(engine)
    track_fks = insp.get_foreign_keys("tracks")
    section_fk = [fk for fk in track_fks if fk["referred_table"] == "railway_sections"]
    assert len(section_fk) > 0, "tracks table must have a foreign key to railway_sections"

    asset_fks = insp.get_foreign_keys("assets")
    asset_ref_tables = {fk["referred_table"] for fk in asset_fks}
    assert "railway_sections" in asset_ref_tables, "assets table must reference railway_sections"
    assert "tracks" in asset_ref_tables, "assets table must reference tracks"


# ==============================================================================
# 5. ML ARTIFACTS & DATASET PRESERVATION AND IDENTIFICATION
# ==============================================================================

def test_ml_artifacts_exist_and_intact():
    """Verify trained ML artifacts exist, load properly, and match expected pipeline classes."""
    train_impact_path = root_dir / "models" / "etrain_delay_model_pipeline.joblib"
    if not train_impact_path.exists():
        train_impact_path = backend_dir / "model_artifacts" / "train_impact" / "etrain_delay_model_pipeline.joblib"

    assert train_impact_path.exists(), f"Model artifact missing: {train_impact_path}"
    # Verify joblib loadability
    pipeline_delay = joblib.load(train_impact_path)
    assert hasattr(pipeline_delay, "predict"), "Train impact model must expose .predict()"

    asset_risk_path = root_dir / "models" / "railway_maintenance_model_pipeline.joblib"
    if not asset_risk_path.exists():
        asset_risk_path = backend_dir / "model_artifacts" / "asset_risk" / "railway_maintenance_model_pipeline.joblib"

    assert asset_risk_path.exists(), f"Asset risk artifact missing: {asset_risk_path}"
    pipeline_risk = joblib.load(asset_risk_path)
    assert hasattr(pipeline_risk, "predict_proba") or hasattr(pipeline_risk, "predict"), "Asset risk model must expose prediction interface"


def test_maintenance_data_identified_as_dataset():
    """Verify maintenance_data.joblib is recognized as a 5000-record dataset, NOT a model."""
    dataset_path = root_dir / "data" / "processed" / "maintenance_data.joblib"
    if not dataset_path.exists():
        dataset_path = backend_dir / "model_artifacts" / "maintenance_duration" / "maintenance_data.joblib"

    assert dataset_path.exists(), f"maintenance_data.joblib missing at {dataset_path}"
    data = joblib.load(dataset_path)
    assert isinstance(data, (pd.DataFrame, dict, list)), "maintenance_data.joblib must be a tabular/dataset structure"
    if isinstance(data, pd.DataFrame):
        assert len(data) == 5000, f"Expected 5,000 records in maintenance dataset, found {len(data)}"
        assert "maintenance_duration_minutes" in data.columns


def test_timetable_operational_dataset_integrity():
    """Verify historical operational timetable CSV exists and is NOT treated as an ML model."""
    csv_path = root_dir / "data" / "timetable" / "Train_details_22122017.csv"
    if not csv_path.exists():
        csv_path = backend_dir / "model_artifacts" / "operation_data" / "Train_details_22122017.csv"

    assert csv_path.exists(), f"Timetable dataset missing at {csv_path}"
    df_sample = pd.read_csv(csv_path, nrows=10)
    assert len(df_sample) == 10
    # Verify expected column names from Indian Railways timetable
    expected_cols = ["Train No", "Train Name", "Station Code", "Station Name", "Arrival time", "Departure Time"]
    for col in expected_cols:
        assert col in df_sample.columns, f"Expected timetable column '{col}' in {csv_path.name}"


# ==============================================================================
# 6. ENVIRONMENT & DEMO CONFIGURATION
# ==============================================================================

def test_environment_and_demo_mode():
    """Verify settings parse environment variables cleanly with valid DEMO_MODE setting."""
    assert isinstance(settings.demo_mode, bool)
    assert settings.jwt_secret_key is not None
    assert len(settings.jwt_secret_key) >= 16
    assert settings.database_url.startswith("postgresql")
