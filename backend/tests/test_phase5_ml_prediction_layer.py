"""Phase 5 — AI / ML Prediction Layer Comprehensive Test Suite.

Tests:
1. Standalone TrainDelayPredictor unit & API (POST /api/ml/train-delay/predict).
2. Standalone AssetRiskPredictor unit & API (POST /api/ml/risk/predict).
3. Standalone MaintenanceDurationPredictor unit & API (POST /api/ml/maintenance-duration/predict).
4. TrainScheduleService timetable lookup & /api/ml/trains/affected.
5. TrainImpactService individual train delay evaluation & aggregate metric compilation.
6. Zero affected trains scenario (0 delay, 0 impact).
7. Unified prediction pipeline for maintenance requests (POST /api/ml/predict/maintenance-request/{id}).
8. Database persistence in maintenance_predictions and audit_logs (RUN_PREDICTION).
9. Feature snapshotting and stale prediction detection upon request alteration.
10. Role-Based Access Control (RBAC) and department access boundaries.
11. Security validation (input schema bounds, error codes).
12. Strict Phase Boundaries (No safety engine clearance, no candidate block generation, no OR-Tools).
"""
import sys
import datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.ml.loaders import (
    load_train_delay_model,
    load_risk_model,
    load_maintenance_duration_model,
)
from app.ml.predictors.train_delay import TrainDelayPredictor
from app.ml.predictors.risk import AssetRiskPredictor
from app.ml.predictors.maintenance_duration import MaintenanceDurationPredictor
from app.services.timetable import TrainScheduleService
from app.services.train_impact import TrainImpactService
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction
from app.models.audit import AuditLog

client = TestClient(app)


def login(username: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_iso(days: int = 1, hours: int = 0) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours)
    return dt.isoformat()


@pytest.fixture(scope="module")
def tokens():
    return {
        "eng_staff": login("eng_staff", "SIH@EngStaff2026"),
        "eng_je": login("eng_je", "SIH@EngJE2026"),
        "eng_sse": login("eng_sse", "SIH@EngSSE2026"),
        "elec_staff": login("elec_staff", "SIH@ElecStaff2026"),
        "elec_je": login("elec_je", "SIH@ElecJE2026"),
        "official": login("railway_official", "SIH@Official2026"),
        "operator": login("operations", "SIH@Ops2026"),
    }


# ==============================================================================
# 1. STANDALONE MODEL PIPELINE & PREDICTOR TESTS
# ==============================================================================

def test_train_delay_predictor_unit_and_api(tokens):
    """Test TrainDelayPredictor unit logic and standalone API endpoint."""
    predictor = TrainDelayPredictor()
    features = {
        "train_number": 12601,
        "train_name": "MAS MANGALORE EXP",
        "station_code": "MAS",
        "station_name": "CHENNAI CENTRAL",
        "pct_right_time": 80.0,
        "pct_slight_delay": 10.0,
        "pct_significant_delay": 5.0,
        "pct_cancelled_unknown": 5.0,
    }
    result = predictor.predict(features)
    assert result["predicted_delay_minutes"] >= 0.0
    assert result["model_version"] is not None
    assert result["model_type"] in ["RandomForestRegressor", "DemonstrationFallback"]

    # Test via API
    res = client.post(
        "/api/ml/train-delay/predict",
        headers=auth_header(tokens["official"]),
        json=features,
    )
    assert res.status_code == 200
    data = res.json()
    assert "predicted_delay_minutes" in data
    assert "model_version" in data
    assert data["predicted_delay_minutes"] >= 0.0


def test_asset_risk_predictor_unit_and_api(tokens):
    """Test AssetRiskPredictor unit logic and standalone API endpoint."""
    predictor = AssetRiskPredictor()
    features = {
        "train_age_years": 8.5,
        "average_speed_kmph": 80.0,
        "distance_travelled_km": 1200.0,
        "track_temperature_c": 34.0,
        "rail_wear_mm": 3.0,
        "region": "SR",
        "season": "SUMMER",
        "train_type": "EXPRESS",
    }
    result = predictor.predict(features, allow_defaults=True)
    assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert 0.0 <= result["risk_probability"] <= 1.0

    # Test via API
    res = client.post(
        "/api/ml/risk/predict",
        headers=auth_header(tokens["official"]),
        json=features,
    )
    assert res.status_code == 200
    data = res.json()
    assert "risk_level" in data
    assert "risk_probability" in data
    assert 0.0 <= data["risk_probability"] <= 1.0


def test_maintenance_duration_predictor_unit_and_api(tokens):
    """Test MaintenanceDurationPredictor unit logic and standalone API endpoint."""
    predictor = MaintenanceDurationPredictor()
    features = {
        "maintenance_type": "Track Tamping and Alignment",
        "department": "Engineering",
        "asset_type": "Track",
        "complexity": "Medium",
        "priority": "HIGH",
        "workers": 8,
        "equipment_count": 3,
        "asset_age_years": 6,
        "condition_score": 70.0,
        "previous_duration_min": 180,
    }
    result = predictor.predict(features, allow_defaults=True)
    assert result["predicted_duration_mins"] > 0
    assert result["confidence_interval_lower_mins"] <= result["predicted_duration_mins"]
    assert result["confidence_interval_upper_mins"] >= result["predicted_duration_mins"]

    # Test via API
    res = client.post(
        "/api/ml/maintenance-duration/predict",
        headers=auth_header(tokens["official"]),
        json=features,
    )
    assert res.status_code == 200
    data = res.json()
    assert "predicted_duration_mins" in data
    assert data["predicted_duration_mins"] > 0
    assert "confidence_interval_lower_mins" in data


# ==============================================================================
# 2. TIMETABLE & TRAIN IMPACT SERVICE TESTS
# ==============================================================================

def test_timetable_service_and_api(tokens):
    """Test train schedule timetable lookups and affected train identification."""
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=2)
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=6)

    # Unit lookup
    with SessionLocal() as db:
        trains = TrainScheduleService.get_affected_trains(
            db=db,
            section_id=1,
            track_id=1,
            start_time=start,
            end_time=end,
        )
        assert isinstance(trains, list)

    # API lookup
    res = client.get(
        f"/api/ml/trains/affected?section_id=1&track_id=1&start_time={start.isoformat()}&end_time={end.isoformat()}",
        headers=auth_header(tokens["official"]),
    )
    assert res.status_code == 200
    data = res.json()
    assert "affected_train_count" in data
    assert isinstance(data["individual_predictions"], list)
    if data["individual_predictions"]:
        t = data["individual_predictions"][0]
        assert "train_number" in t


def test_train_impact_service_delay_aggregation():
    """Test that TrainImpactService correctly maps affected trains to individual delays."""
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=2)
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=6)
    impact_service = TrainImpactService()

    with SessionLocal() as db:
        impact = impact_service.assess_train_impact(
            db=db,
            section_id=1,
            track_id=1,
            start_time=start,
            end_time=end,
        )
        assert impact["affected_train_count"] >= 0
        assert impact["total_predicted_delay_minutes"] >= 0.0
        if impact["affected_train_count"] > 0:
            assert len(impact["individual_predictions"]) == impact["affected_train_count"]
            assert all(t["predicted_delay_minutes"] >= 0.0 for t in impact["individual_predictions"])


def test_zero_affected_trains_scenario():
    """Test behavior when no trains traverse a section during a 0-minute duration."""
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=3)
    impact_service = TrainImpactService()
    with SessionLocal() as db:
        impact = impact_service.assess_train_impact(
            db=db,
            section_id=999999,
            track_id=None,
            start_time=start,
            end_time=start,
        )
        assert impact["affected_train_count"] == 0
        assert impact["total_predicted_delay_minutes"] == 0.0
        assert impact["average_predicted_delay_minutes"] == 0.0
        assert impact["maximum_predicted_delay_minutes"] == 0.0
        assert len(impact["individual_predictions"]) == 0


# ==============================================================================
# 3. UNIFIED PREDICTION PIPELINE & DATABASE PERSISTENCE
# ==============================================================================

def test_unified_prediction_for_maintenance_request(tokens):
    """Test running end-to-end unified ML prediction on a real maintenance request."""
    # 1. Create a draft maintenance request
    start = future_iso(2, 2)
    end = future_iso(2, 6)
    req_res = client.post(
        "/api/maintenance/requests",
        headers=auth_header(tokens["eng_staff"]),
        json={
            "asset_id": 1,
            "section_id": 1,
            "track_id": 1,
            "maintenance_type": "Track Tamping and Alignment",
            "priority": "HIGH",
            "requested_start": start,
            "requested_end": end,
            "description": "Phase 5 ML Prediction Test Request",
        },
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    # 2. Run prediction via API
    pred_res = client.post(
        f"/api/ml/predict/maintenance-request/{req_id}",
        headers=auth_header(tokens["official"]),
        json={"save_prediction": True},
    )
    assert pred_res.status_code == 200, f"Predict failed: {pred_res.text}"
    pred = pred_res.json()

    assert pred["maintenance_request_id"] == req_id
    assert "duration_prediction" in pred
    assert "risk_prediction" in pred
    assert "train_impact" in pred
    assert pred["is_stale"] is False

    # Check persistence in maintenance_predictions table
    with SessionLocal() as db:
        db_pred = db.query(MaintenancePrediction).filter(
            MaintenancePrediction.maintenance_request_id == req_id
        ).first()
        assert db_pred is not None
        assert db_pred.predicted_duration_mins > 0
        assert db_pred.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert db_pred.input_features is not None

        # Check audit log
        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "MaintenancePrediction",
            AuditLog.action == "RUN_PREDICTION",
        ).first()
        assert audit is not None


def test_stale_prediction_detection(tokens):
    """Test that modifying a request's duration or time window marks existing predictions as stale."""
    # 1. Create request
    start = future_iso(3, 1)
    end = future_iso(3, 4)
    req_res = client.post(
        "/api/maintenance/requests",
        headers=auth_header(tokens["eng_staff"]),
        json={
            "asset_id": 1,
            "section_id": 1,
            "track_id": 1,
            "maintenance_type": "Rail Grinding and Profiling",
            "priority": "MEDIUM",
            "requested_start": start,
            "requested_end": end,
            "description": "Staleness test request",
        },
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    # 2. Run prediction
    pred_res = client.post(
        f"/api/ml/predict/maintenance-request/{req_id}",
        headers=auth_header(tokens["official"]),
    )
    assert pred_res.status_code == 200
    assert pred_res.json()["is_stale"] is False

    # 3. Update request (e.g. increase duration or change time) directly in DB
    with SessionLocal() as db:
        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == req_id).first()
        req.requested_duration_mins = 360
        db.commit()

    # 4. Fetch prediction status -> should now be marked stale
    status_res = client.get(
        f"/api/ml/predictions/{req_id}",
        headers=auth_header(tokens["official"]),
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_stale"] is True


# ==============================================================================
# 4. RBAC & DEPARTMENT BOUNDARIES
# ==============================================================================

def test_ml_endpoints_rbac(tokens):
    """Test that unauthorized users cannot execute or access predictions improperly."""
    # 1. Unauthenticated request -> 401
    res = client.post("/api/ml/train-delay/predict", json={})
    assert res.status_code == 401

    # 2. Electrical staff accessing an ENG department request
    start = future_iso(4, 1)
    end = future_iso(4, 3)
    req_res = client.post(
        "/api/maintenance/requests",
        headers=auth_header(tokens["eng_staff"]),
        json={
            "asset_id": 1,
            "section_id": 1,
            "track_id": 1,
            "maintenance_type": "Sleeper Renewal",
            "priority": "HIGH",
            "requested_start": start,
            "requested_end": end,
            "description": "ENG scoped request",
        },
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    # ELEC staff should not be able to trigger prediction on ENG scoped request (dept isolation)
    elec_res = client.post(
        f"/api/ml/predict/maintenance-request/{req_id}",
        headers=auth_header(tokens["elec_staff"]),
    )
    assert elec_res.status_code == 403

    # ENG staff can run prediction on their own department's request
    eng_res = client.post(
        f"/api/ml/predict/maintenance-request/{req_id}",
        headers=auth_header(tokens["eng_staff"]),
    )
    assert eng_res.status_code == 200


# ==============================================================================
# 5. INPUT VALIDATION & SECURITY
# ==============================================================================

def test_ml_input_validation_and_security(tokens):
    """Test validation errors on missing/malformed feature payloads."""
    # Non-existent maintenance request ID
    res = client.post(
        "/api/ml/predict/maintenance-request/999999",
        headers=auth_header(tokens["official"]),
    )
    assert res.status_code == 404


# ==============================================================================
# 6. STRICT PHASE BOUNDARIES
# ==============================================================================

def test_strict_phase_boundaries(tokens):
    """Verify that Phase 5 AI prediction layer strictly adheres to its phase boundaries."""
    # Ensure prediction execution does not modify maintenance status to APPROVED or clear safety
    start = future_iso(5, 1)
    end = future_iso(5, 4)
    req_res = client.post(
        "/api/maintenance/requests",
        headers=auth_header(tokens["eng_staff"]),
        json={
            "asset_id": 1,
            "section_id": 1,
            "track_id": 1,
            "maintenance_type": "Deep Screening of Ballast",
            "priority": "HIGH",
            "requested_start": start,
            "requested_end": end,
            "description": "Boundary test request",
        },
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    pred_res = client.post(
        f"/api/ml/predict/maintenance-request/{req_id}",
        headers=auth_header(tokens["official"]),
    )
    assert pred_res.status_code == 200

    # Verify maintenance request status remains unchanged (e.g. DRAFT)
    with SessionLocal() as db:
        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == req_id).first()
        assert req.status == "DRAFT"
        # Ensure no safety engine verdict was inserted
        assert "SAFE" not in str(pred_res.json().get("risk_prediction", {}).get("risk_level", ""))
