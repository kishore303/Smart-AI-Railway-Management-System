# SIH26027 — AI-Powered Automatic Railway Block Planning, Integrated Maintenance Coordination & Emergency Response System

> **Core System Principle:**  
> *"AI predicts, rules validate, optimization selects, and railway officials make the final decision."*

A centralized decision-support platform designed for Indian Railways maintenance coordination, multi-department block planning, timetable conflict resolution, and emergency response orchestration.

---

## 1. System Architecture & Tech Stack

```
   FRONTEND (Next.js 14 + TypeScript + Tailwind CSS + Lucide Icons)
                               │
                       HTTP / REST API (JWT)
                               ▼
           BACKEND (Python FastAPI + Pydantic v2 + SQLAlchemy 2.0)
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ML PREDICTION       SAFETY ENGINE       OR-TOOLS CP-SAT
   (scikit-learn)       (Rule Validator)       (Optimizer)
            │                  │                  │
            └──────────────────┼──────────────────┘
                               ▼
        DATABASE (PostgreSQL 18+ with PostGIS 3.6.2 Spatial Extension)
```

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide React icons.
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Pydantic v2 Settings.
- **Database:** PostgreSQL 18 with PostGIS 3.6.2 (`SRID 4326` for spatial data).
- **Optimization:** Google OR-Tools CP-SAT (Constraint Satisfaction & Optimization).
- **Machine Learning:** scikit-learn trained pipelines (`joblib` artifacts).
- **Asynchronous & Caching:** Redis & Celery foundation.

---

## 2. Directory Structure

```
IRCTC/
├── frontend/                     # Next.js 14 web application
│   ├── app/                      # App router pages (login, dashboard, review, etc.)
│   ├── components/               # Reusable UI components & Sidebar navigation
│   └── lib/                      # API client, auth context & TypeScript definitions
│
├── backend/                      # FastAPI backend application
│   ├── app/
│   │   ├── api/                  # API routers (auth, maintenance, blocks, safety, etc.)
│   │   ├── core/                 # Config, security, RBAC & structured logging
│   │   ├── database/             # SQLAlchemy session & Base definition
│   │   ├── models/               # 29 SQLAlchemy database models matching PostgreSQL schema
│   │   ├── schemas/              # Pydantic validation schemas
│   │   └── main.py               # Application entry point & health endpoints
│   ├── model_artifacts/          # Original ML artifacts & raw inputs
│   ├── scripts/                  # DB initialization, user seeding & model verification
│   ├── sql/                      # Authoritative SQL schema & migration scripts
│   └── tests/                    # Automated pytest test suites
│
├── data/                         # Data directory (structured separation)
│   ├── raw/                      # Raw incoming data
│   ├── processed/                # Preprocessed datasets (e.g. maintenance_data.joblib)
│   ├── timetable/                # Historical operational timetable data (CSV)
│   └── demo/                     # Demonstration & synthetic test fixtures
│
├── models/                       # Trained ML model pipelines (.joblib)
│   ├── etrain_delay_model_pipeline.joblib          # Delay regression pipeline
│   ├── railway_maintenance_model_pipeline.joblib    # Asset risk classification pipeline
│   └── maintenance_data.joblib                     # 5k-record duration training dataset
│
├── .env.example                  # Environment variables template
└── README.md                     # Project documentation
```

---

## 3. Database & Domain Model Foundation

The PostgreSQL + PostGIS database schema provides **29 core tables**, 12 custom enums, and full spatial geometry columns (`SRID 4326`):

1. **Hierarchy & Spatial Network:**  
   `stations` (Point) $\to$ `railway_sections` (LineString) $\to$ `tracks` (LineString) $\to$ `assets` (Point). Multi-track per section is fully supported.
2. **Maintenance & Safety:**  
   `maintenance_requests`, `maintenance_predictions`, `block_requests`, `block_candidates`, and the critical `safety_validations` table with JSONB validation checks, preventing unsafe candidates from entering the optimizer.
3. **13-Role Granular RBAC:**  
   Covers 3 Engineering departments (`ENG`, `ELEC`, `SNT`) each with a 3-tier hierarchy (`MAINTENANCE_STAFF` $\to$ `JUNIOR_ENGINEER` $\to$ `SENIOR_SECTION_ENGINEER`) plus operational roles (`OPERATOR`, `CONTROLLER`, `AUTHORIZED_OFFICIAL`, `EMERGENCY_OPERATOR`).

---

## 4. ML Artifacts & Operational Datasets

| Asset Name | Type | Size | Description / Purpose |
| :--- | :--- | :--- | :--- |
| `etrain_delay_model_pipeline.joblib` | ML Model (RandomForest Regression) | 11.2 MB | Predicts train delay in minutes based on traffic and block duration. |
| `railway_maintenance_model_pipeline.joblib` | ML Model (RandomForest Classification) | 162.1 MB | Predicts asset operational failure risk score and risk category. |
| `maintenance_data.joblib` | **Dataset** (5,000 records) | 291 KB | Historical maintenance dataset for training duration models. |
| `Train_details_22122017.csv` | **Operational Dataset** (CSV) | 16.7 MB | Historical Indian Railways operational timetable data for schedule conflict analysis. |

*Disclaimer: The operational timetable dataset contains historical reference records for evaluation and simulation within this decision-support prototype.*

---

## 5. Quick Start & Verification

### Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # On Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt

# Initialize Database & Seed 13 Demo Accounts
python scripts/init_db.py
python scripts/seed_users.py
python scripts/verify_models.py

### Master 10-Phase Test Suite
```bash
cd backend
python -m pytest tests/test_phase1_foundation.py tests/test_phase2_auth_rbac.py tests/test_phase3_maintenance_workflow.py tests/test_phase4_coordination_integration.py tests/test_phase5_ml_prediction_layer.py tests/test_phase6_block_candidates_safety_engine.py tests/test_phase7_ortools_optimization_engine.py tests/test_phase8_official_approval_center.py tests/test_phase9_emergency_control.py tests/test_phase10_final_integration.py -v
# 141 / 141 Tests Passing (100% Pass Rate)
```

### Health & Diagnostic Check Endpoints
- Application Health: `http://localhost:8000/health`
- Database & PostGIS Status: `http://localhost:8000/health/db`
- Dependency Diagnostics (DB, PostGIS, ML Models, OR-Tools CP-SAT): `http://localhost:8000/health/dependencies`

### Frontend Setup
```bash
cd frontend
npm install
npm run build                    # 28/28 Static & Dynamic Routes Built Successfully
npm run dev                      # Runs on http://localhost:3000
```

---

## 6. Complete 10-Phase Implementation Matrix

| Phase | Core Capabilities | Test Status |
| :--- | :--- | :--- |
| **Phase 1** | PostgreSQL 18 + PostGIS 3.6.2 (29 tables, SRID 4326), Model verification | **100% Verified** |
| **Phase 2** | JWT Security, 13-Role RBAC, Department data isolation, Self-approval protection | **100% Verified** |
| **Phase 3** | Maintenance Request Lifecycle, JE/SSE Technical Reviews, Revision loops | **100% Verified** |
| **Phase 4** | Cross-Department Coordination (ENG/ELEC/SNT), Spatial Overlap Detection | **100% Verified** |
| **Phase 5** | ML Pipelines (Train Delay Regression, Asset Failure Classification, Timetable queries) | **100% Verified** |
| **Phase 6** | Deterministic Railway Safety Engine (11 rules, track/corridor conflict gating) | **100% Verified** |
| **Phase 7** | Google OR-Tools CP-SAT Integer Programming Optimization Engine | **100% Verified** |
| **Phase 8** | Railway Official Approval Center (Approve/Modify/Reject, Section 1-12 Inspection) | **100% Verified** |
| **Phase 9** | Emergency Control & Fast-Track Re-Planning, Incident Management, Corridor Isolation | **100% Verified** |
| **Phase 10** | Digital Twin, What-If Studio, Manual vs AI Benchmark, Block Marketplace, 9-Dim Analytics | **100% Verified (141/141)** |
