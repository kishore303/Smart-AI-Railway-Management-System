# SIH26027 — AI-Powered Automatic Railway Block Planning, Integrated Maintenance Coordination & Emergency Response System

Centralized decision-support platform: **ML predicts → Safety Engine validates → OR-Tools optimizes → Authorized Railway Official decides**

## Module 1 — Database & Core Models (Current)

### Database
- PostgreSQL 18.4 + PostGIS 3.6.2 (SRID 4326)
- Database: `sih26027`
- 28 core tables + `spatial_ref_sys` (PostGIS system) + 1 view `section_traffic_stats`
- 12 enums, PostGIS `POINT` (stations/assets/resources/incidents) and `LINESTRING` (sections/tracks)
- Enums corrected: `OPERATOR` / `CONTROLLER` (not old `OPERATIONS_OPERATOR` / `CONTROL_CONTROLLER`)
- Seed: 7 departments, 10 department_roles

### Backend
- FastAPI + SQLAlchemy 2.0 + GeoAlchemy2 + psycopg2 + Pydantic Settings
- Models in `backend/app/models/` exactly match authoritative SQL (constraints, FKs, checks preserved)
- DB connection via `backend/app/database.py` (DATABASE_URL in `.env`)
- PostGIS extension enabled via `scripts/init_db.py`

### Quick Start
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL / JWT_SECRET if needed
python scripts/init_db.py      # create sih26027 + apply authoritative_schema.sql
python scripts/verify_models.py
python tests/test_db_connection.py
python tests/test_models.py
uvicorn app.main:app --reload --port 8000
# health: http://localhost:8000/health  http://localhost:8000/health/db
```

### ML Artifacts (Backend-side only, never frontend)
- `model_artifacts/train_impact/etrain_delay_model_pipeline.joblib` (RandomForest, sklearn 1.6.1)
- `model_artifacts/asset_risk/railway_maintenance_model_pipeline.joblib`
- `model_artifacts/maintenance_duration/maintenance_data.joblib`
- Adapter/predictor implementation begins in Module 6.

### Next Modules
2. Authentication & RBAC — NOT yet implemented (compliance with module-by-module rule)
