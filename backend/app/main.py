from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.config import settings

app = FastAPI(
    title="SIH26027 Railway Block Planning — API",
    version="1.0.0 — SIH26027 Master Integrated Release",
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

# Routers
from app.api import auth as auth_api  # noqa: E402
from app.api import users as users_api  # noqa: E402
from app.api import maintenance as maintenance_api  # noqa: E402
from app.api import ml as ml_api  # noqa: E402
from app.api import blocks as blocks_api  # noqa: E402
from app.api import integration as integration_api  # noqa: E402
from app.api import safety as safety_api  # noqa: E402
from app.api import optimization as optimization_api  # noqa: E402
from app.api import approval as approval_api  # noqa: E402
from app.api import recommendations as recommendations_api  # noqa: E402
from app.api import execution as execution_api  # noqa: E402
from app.api import notifications as notifications_api  # noqa: E402
from app.api import simulation as simulation_api  # noqa: E402
from app.api import dashboard as dashboard_api  # noqa: E402
from app.api import spatial as spatial_api  # noqa: E402
from app.api import emergency as emergency_api  # noqa: E402
from app.api import analytics as analytics_api  # noqa: E402
from app.api import marketplace as marketplace_api  # noqa: E402
# maintenance_stub kept for backward compat
from app.api import maintenance_stub as maint_stub  # noqa: E402

app.include_router(auth_api.router)
app.include_router(users_api.router)
app.include_router(maintenance_api.router)
app.include_router(ml_api.router)
app.include_router(blocks_api.router)
app.include_router(integration_api.router)
app.include_router(safety_api.router)
app.include_router(optimization_api.router)
app.include_router(approval_api.router)
app.include_router(recommendations_api.router)
app.include_router(execution_api.router)
app.include_router(notifications_api.router)
app.include_router(simulation_api.router)
app.include_router(dashboard_api.router)
app.include_router(spatial_api.router)
app.include_router(emergency_api.router)
app.include_router(analytics_api.router)
app.include_router(marketplace_api.router)
app.include_router(maint_stub.router)


from app.core.logging_config import logger

@app.get("/health")
def health():
    return {
        "status": "online",
        "app": settings.app_name,
        "environment": settings.app_env,
        "demo_mode": settings.demo_mode,
        "version": app.version,
    }


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        # PostGIS check
        try:
            result = db.execute(text("SELECT postgis_version()"))
            postgis_version = result.scalar()
        except Exception:
            postgis_version = "not-installed"

        # Count tables
        result = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
        table_count = result.scalar()

        return {
            "status": "connected",
            "database": "postgresql",
            "postgis": postgis_version,
            "public_tables": table_count,
            "database_ready": True,
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "database": "disconnected",
            "message": "Database connection unavailable",
            "database_ready": False,
        }


@app.get("/health/dependencies")
def health_dependencies(db: Session = Depends(get_db)):
    # 1. Database
    db_ok = False
    table_count = 0
    postgis_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        t_res = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
        table_count = t_res.scalar() or 0
        p_res = db.execute(text("SELECT postgis_version()"))
        postgis_ok = bool(p_res.scalar())
    except Exception as e:
        logger.error(f"DB Dependency Check Error: {e}")

    # 2. ML Models
    ml_models = {}
    try:
        from app.ml.loaders import load_train_impact, load_asset_risk, load_maintenance_duration_model
        load_train_impact()
        load_asset_risk()
        load_maintenance_duration_model()
        ml_models = {
            "train_impact": {"status": "LOADED", "cached": True, "type": "RandomForestRegressor Pipeline"},
            "asset_risk": {"status": "LOADED", "cached": True, "type": "RandomForestClassifier Pipeline"},
            "maintenance_duration": {"status": "LOADED", "cached": True, "type": "RandomForestRegressor Pipeline"},
        }
    except Exception as e:
        ml_models = {"status": "ERROR", "error": str(e)}

    # 3. OR-Tools
    ortools_ok = False
    try:
        from ortools.sat.python import cp_model
        _m = cp_model.CpModel()
        ortools_ok = True
    except Exception as e:
        logger.error(f"OR-Tools Check Error: {e}")

    return {
        "status": "healthy" if db_ok and ortools_ok else "degraded",
        "database": {
            "connected": db_ok,
            "postgis_enabled": postgis_ok,
            "public_tables": table_count,
        },
        "ml_engine": {
            "models_count": len(ml_models) if isinstance(ml_models, dict) else 0,
            "models": ml_models,
        },
        "optimization_engine": {
            "ortools_cp_sat": "READY" if ortools_ok else "UNAVAILABLE",
        },
        "safety_engine": {
            "status": "READY",
            "rules_count": 9,
        },
    }
