from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction, MlModelRegistry
from app.models.audit import AuditLog

from app.ml.predictors.train_delay import TrainDelayPredictor
from app.ml.predictors.risk import AssetRiskPredictor
from app.ml.predictors.maintenance_duration import MaintenanceDurationPredictor
from app.ml.predictors.unified import MLPredictionService
from app.services.timetable import TrainScheduleService
from app.services.train_impact import TrainImpactService
from app.ml.predictors.service import persist_prediction, ensure_registry
from app.ml.loaders import model_info, clear_cache

router = APIRouter(prefix="/api/ml", tags=["ml"])

train_delay_predictor = TrainDelayPredictor()
risk_predictor = AssetRiskPredictor()
duration_predictor = MaintenanceDurationPredictor()
train_impact_service = TrainImpactService()
unified_service = MLPredictionService()


def _check_request_access(db: Session, user: User, request_id: int) -> MaintenanceRequest:
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
    if not can_access_department_resource(user, req.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return req


# ==================== Model Registry & Artifacts ====================

@router.get("/models")
def list_models(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    ensure_registry(db)
    rows = db.query(MlModelRegistry).order_by(MlModelRegistry.model_type).all()
    return [
        {
            "model_type": r.model_type,
            "version": r.version,
            "artifact_filename": r.artifact_filename,
            "is_demo": r.is_demo,
            "is_active": r.is_active,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.get("/models/{model_type}")
def get_model_details(model_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    ensure_registry(db)
    m = db.query(MlModelRegistry).filter(MlModelRegistry.model_type == model_type.upper()).first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model type '{model_type}' not found")
    
    info = {}
    if m.model_type == "TRAIN_IMPACT":
        info = {
            "model_name": "etrain_delay_model_pipeline",
            "type": "RandomForestRegressor Pipeline",
            "target": "predicted_delay_minutes",
            "features": TrainDelayPredictor.ALL_COLUMNS,
            "artifact_status": model_info("train_impact"),
        }
    elif m.model_type == "ASSET_RISK":
        info = {
            "model_name": "railway_maintenance_model_pipeline",
            "type": "RandomForestClassifier Pipeline",
            "target": "risk_class (0/1) & risk_probability",
            "features": AssetRiskPredictor.ALL_COLUMNS,
            "artifact_status": model_info("asset_risk"),
        }
    elif m.model_type == "MAINTENANCE_DURATION":
        info = {
            "model_name": "maintenance_duration_model",
            "type": "RandomForestRegressor Pipeline",
            "target": "maintenance_duration_minutes",
            "features": MaintenanceDurationPredictor.ALL_COLUMNS,
            "artifact_status": model_info("maintenance_duration_model"),
        }
    
    return {
        "model_type": m.model_type,
        "version": m.version,
        "artifact_filename": m.artifact_filename,
        "is_demo": m.is_demo,
        "is_active": m.is_active,
        "notes": m.notes,
        **info,
    }


@router.get("/artifacts/status")
def artifact_status(current_user: User = Depends(get_current_active_user)):
    return {
        "train_impact": model_info("train_impact"),
        "asset_risk": model_info("asset_risk"),
        "maintenance_duration_model": model_info("maintenance_duration_model"),
        "maintenance_duration_data": model_info("maintenance_duration_data"),
        "principle": "AI predicts -> Safety validates -> OR-Tools optimizes -> Official decides. AI never approves.",
    }


# ==================== Standalone Predictors ====================

@router.post("/train-delay/predict")
@router.post("/predict/train-impact")
def predict_train_delay(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = train_delay_predictor.predict(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    persisted_id = None
    if maintenance_request_id:
        mp = persist_prediction(db, maintenance_request_id, result, current_user.id)
        persisted_id = mp.id
    else:
        log = AuditLog(user_id=current_user.id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=None, description=f"Direct train-delay prediction {result['model_version']}")
        db.add(log)
        db.commit()

    return {
        **result,
        "persisted_id": persisted_id,
        "disclaimer": "AI prediction only — does not approve block, safety/optimization required",
    }


@router.post("/risk/predict")
@router.post("/predict/asset-risk")
def predict_risk(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = risk_predictor.predict(payload, allow_defaults=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    persisted_id = None
    if maintenance_request_id:
        mp = persist_prediction(db, maintenance_request_id, result, current_user.id)
        persisted_id = mp.id
    else:
        log = AuditLog(user_id=current_user.id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=None, description=f"Direct asset-risk {result['model_version']}")
        db.add(log)
        db.commit()

    return {
        **result,
        "persisted_id": persisted_id,
        "disclaimer": "AI prediction only — operational risk metric, does not approve or reject block",
    }


@router.post("/maintenance-duration/predict")
@router.post("/predict/maintenance-duration")
def predict_duration(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = duration_predictor.predict(payload, allow_defaults=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    persisted_id = None
    if maintenance_request_id:
        mp = persist_prediction(db, maintenance_request_id, result, current_user.id)
        persisted_id = mp.id
    else:
        log = AuditLog(user_id=current_user.id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=None, description=f"Production duration prediction {result['model_version']}")
        db.add(log)
        db.commit()

    return {
        **result,
        "persisted_id": persisted_id,
        "disclaimer": "AI prediction only — maintenance duration metric, final block duration determined in planning.",
    }


# ==================== Timetable Affected Trains ====================

@router.get("/trains/affected")
def query_affected_trains(
    section_id: int = Query(...),
    track_id: Optional[int] = Query(None),
    start_time: str = Query(...),
    end_time: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Query scheduled trains traversing section during window and compute individual delays."""
    try:
        dt_start = datetime.fromisoformat(start_time.replace(" ", "+").replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end_time.replace(" ", "+").replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid ISO timestamp format for start_time or end_time")

    impact_res = train_impact_service.assess_train_impact(
        db=db,
        section_id=section_id,
        track_id=track_id,
        start_time=dt_start,
        end_time=dt_end,
    )
    return impact_res


# ==================== Unified Maintenance Request Prediction ====================

@router.post("/predict/maintenance-request/{request_id}")
def predict_for_maintenance_request(
    request_id: int,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Execute full unified AI prediction for a maintenance request:
    Duration + Risk + Timetable Affected Trains + Delay Models -> Persist -> Return.
    """
    req = _check_request_access(db, current_user, request_id)
    try:
        result = unified_service.predict_for_maintenance_request(
            db=db,
            maintenance_request_id=request_id,
            user_id=current_user.id,
            custom_inputs=payload or {},
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction pipeline error: {str(e)}")


@router.get("/predictions/{request_id}")
def get_request_predictions(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve historical prediction snapshots and staleness evaluation for a request."""
    req = _check_request_access(db, current_user, request_id)
    rows = (
        db.query(MaintenancePrediction)
        .filter(MaintenancePrediction.maintenance_request_id == request_id)
        .order_by(MaintenancePrediction.predicted_at.desc())
        .all()
    )
    latest = rows[0] if rows else None
    is_stale = unified_service.is_prediction_stale(req, latest)

    return {
        "maintenance_request_id": request_id,
        "is_stale": is_stale,
        "total_predictions": len(rows),
        "latest_prediction": (
            {
                "id": latest.id,
                "asset_risk_score": float(latest.asset_risk_score) if latest.asset_risk_score is not None else None,
                "risk_level": latest.risk_level,
                "predicted_duration_mins": latest.predicted_duration_mins,
                "train_impact_score": float(latest.train_impact_score) if latest.train_impact_score is not None else None,
                "predicted_delay_mins": latest.predicted_delay_mins,
                "affected_train_count": latest.affected_train_count,
                "model_version": latest.model_version,
                "input_features": latest.input_features,
                "predicted_at": latest.predicted_at.isoformat(),
            }
            if latest
            else None
        ),
        "history": [
            {
                "id": r.id,
                "asset_risk_score": float(r.asset_risk_score) if r.asset_risk_score is not None else None,
                "risk_level": r.risk_level,
                "predicted_duration_mins": r.predicted_duration_mins,
                "train_impact_score": float(r.train_impact_score) if r.train_impact_score is not None else None,
                "predicted_delay_mins": r.predicted_delay_mins,
                "affected_train_count": r.affected_train_count,
                "model_version": r.model_version,
                "predicted_at": r.predicted_at.isoformat(),
            }
            for r in rows
        ],
    }
