from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.config import settings

app = FastAPI(
    title="SIH26027 Railway Block Planning — API",
    version="0.16.0 — Emergency Incident CRUD + Bug Fixes",
    description="Decision-support platform: ML predicts → Safety validates → OR-Tools optimizes → Official decides",
)

# CORS for Next.js frontend
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers will be included below
from app.api import auth as auth_api  # noqa: E402
from app.api import users as users_api  # noqa: E402
from app.api import maintenance as maintenance_api  # noqa: E402
from app.api import ml as ml_api  # noqa: E402
from app.api import blocks as blocks_api  # noqa: E402
from app.api import integration as integration_api  # noqa: E402
from app.api import safety as safety_api  # noqa: E402
from app.api import optimization as optimization_api  # noqa: E402
from app.api import recommendations as recommendations_api  # noqa: E402
from app.api import execution as execution_api  # noqa: E402
from app.api import notifications as notifications_api  # noqa: E402
from app.api import simulation as simulation_api  # noqa: E402
from app.api import dashboard as dashboard_api  # noqa: E402
from app.api import spatial as spatial_api  # noqa: E402
from app.api import emergency as emergency_api  # noqa: E402
# maintenance_stub kept for backward compat but new maintenance router is primary
from app.api import maintenance_stub as maint_stub  # noqa: E402

app.include_router(auth_api.router)
app.include_router(users_api.router)
app.include_router(maintenance_api.router)
app.include_router(ml_api.router)
app.include_router(blocks_api.router)
app.include_router(integration_api.router)
app.include_router(safety_api.router)
app.include_router(optimization_api.router)
app.include_router(recommendations_api.router)
app.include_router(execution_api.router)
app.include_router(notifications_api.router)
app.include_router(simulation_api.router)
app.include_router(dashboard_api.router)
app.include_router(spatial_api.router)
app.include_router(emergency_api.router)
app.include_router(maint_stub.router)


@app.get("/health")
def health():
    return {"status": "ok", "module": "1-database-core-models", "postgis": "pending-check"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        # PostGIS check
        try:
            result = db.execute(text("SELECT postgis_version()"))
            version = result.scalar()
        except Exception:
            version = "not-installed"

        # Count tables
        result = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
        table_count = result.scalar()

        return {"status": "ok", "postgis": version, "public_tables": table_count}
    except Exception as e:
        return {"status": "error", "error": str(e)}

