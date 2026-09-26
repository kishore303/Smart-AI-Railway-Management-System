import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User
from app.models.department import Department


client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_token_for_user(db: Session, email: str) -> str:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = db.query(User).first()
    dept = db.query(Department).filter(Department.id == user.department_id).first() if user else None
    dept_code = dept.code if dept and hasattr(dept, "code") else "ENGG"
    return create_access_token(
        data={
            "sub": str(user.id),
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "department_code": dept_code,
        }
    )


@pytest.fixture
def official_headers(db):
    token = get_token_for_user(db, "official@railway.gov.in")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def controller_headers(db):
    token = get_token_for_user(db, "controller@railway.gov.in")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def je_headers(db):
    token = get_token_for_user(db, "je.engg@railway.gov.in")
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# 1. Health & Dependency Diagnostics
# ==========================================
def test_health_dependencies():
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "ml_engine" in data
    assert "optimization_engine" in data
    assert "safety_engine" in data
    assert data["optimization_engine"]["ortools_cp_sat"] == "READY"


# ==========================================
# 2. Comprehensive Analytics Endpoints
# ==========================================
def test_analytics_overview(official_headers):
    response = client.get("/api/analytics/overview", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "kpis" in data
    assert "total_block_requests" in data["kpis"]
    assert "total_affected_trains" in data["kpis"]


def test_analytics_blocks(official_headers):
    response = client.get("/api/analytics/blocks", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "status_distribution" in data
    assert "department_distribution" in data
    assert "duration_distribution" in data


def test_analytics_train_impact(official_headers):
    response = client.get("/api/analytics/train-impact", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "section_delay_impact" in data
    assert "train_fleet_composition" in data


def test_analytics_assets(official_headers):
    response = client.get("/api/analytics/assets", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "health_distribution" in data
    assert "type_summary" in data
    assert "high_risk_assets" in data


def test_analytics_resources(official_headers):
    response = client.get("/api/analytics/resources", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "resource_types" in data
    assert "allocations_by_status" in data
    assert "department_resources" in data


def test_analytics_coordination(official_headers):
    response = client.get("/api/analytics/coordination", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "integration_status_distribution" in data
    assert "department_coordination_pairs" in data


def test_analytics_emergencies(official_headers):
    response = client.get("/api/analytics/emergencies", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "incident_types" in data
    assert "severity_distribution" in data
    assert "workflow_status_distribution" in data


def test_analytics_optimization(official_headers):
    response = client.get("/api/analytics/optimization", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "candidate_safety_gate_distribution" in data
    assert "score_statistics" in data
    assert "solver_engine" in data


def test_analytics_models(official_headers):
    response = client.get("/api/analytics/models", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "evaluation_metrics" in data


# ==========================================
# 3. Block Marketplace & Resource Sharing
# ==========================================
def test_marketplace_blocks_list(official_headers):
    response = client.get("/api/marketplace/blocks", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "marketplace_blocks" in data


def test_marketplace_resource_timeline(official_headers):
    response = client.get("/api/marketplace/resources/timeline", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "resources_count" in data
    assert "timeline" in data


def test_marketplace_join_flow(je_headers):
    blocks_res = client.get("/api/marketplace/blocks", headers=je_headers)
    assert blocks_res.status_code == 200
    blocks_data = blocks_res.json()
    
    if blocks_data["total"] > 0:
        target_b = blocks_data["marketplace_blocks"][0]
        join_payload = {
            "target_block_id": target_b["id"],
            "requesting_department_id": 2 if target_b["primary_department_id"] != 2 else 1,
            "work_type": "OHE Inspection",
            "remarks": "Joint testing of marketplace join flow",
            "estimated_duration_mins": 45,
        }
        res = client.post("/api/marketplace/join", json=join_payload, headers=je_headers)
        assert res.status_code in (200, 400)


# ==========================================
# 4. Digital Twin & What-If Simulations
# ==========================================
def test_digital_twin_state(official_headers):
    response = client.get("/api/simulation/digital-twin/state", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["digital_twin_status"] == "ONLINE_SYNCED"
    assert "counts" in data
    assert "active_corridor_blocks" in data


def test_digital_twin_timeline(official_headers):
    response = client.get("/api/simulation/digital-twin/timeline", headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "timeline_start" in data


def test_what_if_simulation_non_mutating(official_headers):
    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(hours=5)).isoformat()
    end_time = (now + timedelta(hours=7)).isoformat()

    payload = {
        "simulation_name": "Test Simulation Window",
        "section_id": 1,
        "track_id": 1,
        "start_time": start_time,
        "end_time": end_time,
        "duration_mins": 120,
    }

    response = client.post("/api/simulation/what-if", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data
    assert "safety" in data
    assert "feasibility" in data
    assert "disclaimer" in data


def test_compare_scenarios(official_headers):
    payload = {
        "scenarios": [
            {
                "name": "Scenario A: Early Morning",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
                "duration_mins": 90,
            },
            {
                "name": "Scenario B: Afternoon Peak",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
                "duration_mins": 180,
            },
        ]
    }

    response = client.post("/api/simulation/compare", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["scenarios_count"] == 2
    assert "recommended_scenario" in data


def test_manual_vs_ai_benchmark(official_headers):
    now = datetime.now(timezone.utc)
    manual_start = (now + timedelta(hours=2)).isoformat()
    manual_end = (now + timedelta(hours=5)).isoformat()

    payload = {
        "section_id": 1,
        "track_id": 1,
        "manual_start": manual_start,
        "manual_end": manual_end,
        "department_id": 1,
        "work_type": "Track Relaying",
        "duration_mins": 180,
    }

    response = client.post("/api/simulation/manual-vs-ai", json=payload, headers=official_headers)
    assert response.status_code == 200
    data = response.json()
    assert "manual_plan" in data
    assert "ai_optimized_plan" in data
    assert "improvements" in data
    assert "delay_reduction_mins" in data["improvements"]
    assert "optimization_score_gain" in data["improvements"]
    assert "insights" in data
    assert "disclaimer" in data
