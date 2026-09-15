from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.maintenance import MaintenanceRequest
from app.models.audit import AuditLog
from app.ml.adapters.train_impact import TrainImpactAdapter
from app.ml.adapters.asset_risk import AssetRiskAdapter
from app.ml.adapters.maintenance_duration import MaintenanceDurationDemoAdapter
from app.ml.predictors.service import persist_prediction, ensure_registry
from app.ml.loaders import model_info, clear_cache

router = APIRouter(prefix="/api/ml", tags=["ml"])

train_adapter = TrainImpactAdapter()
asset_adapter = AssetRiskAdapter()
duration_adapter = MaintenanceDurationDemoAdapter()


def _check_request_access(db: Session, user: User, request_id: int) -> MaintenanceRequest:
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
    if not can_access_department_resource(user, req.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return req


@router.get("/models")
def list_models(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    ensure_registry(db)
    from app.models.maintenance import MlModelRegistry

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


@router.get("/artifacts/status")
def artifact_status(current_user: User = Depends(get_current_active_user)):
    # MD5 verification — no secrets
    return {
        "train_impact": model_info("train_impact"),
        "asset_risk": model_info("asset_risk"),
        "maintenance_duration_data": model_info("maintenance_duration_data"),
        "principle": "ML predicts -> Safety validates -> OR-Tools optimizes -> Official decides. ML never approves.",
    }


@router.post("/predict/train-impact")
def predict_train_impact(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # RBAC: any authenticated can predict, but if request_id provided, check dept
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    # Support both direct features and request-linked
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = train_adapter.predict(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    # Persist if linked to request
    persisted_id = None
    if maintenance_request_id:
        mp = persist_prediction(db, maintenance_request_id, result, current_user.id)
        persisted_id = mp.id
    else:
        # Audit without persistence
        log = AuditLog(user_id=current_user.id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=None, description=f"Direct train-impact {result['model_version']}")
        db.add(log)
        db.commit()
    return {**result, "persisted_id": persisted_id, "disclaimer": "ML prediction only — does not approve block, safety/optimization required"}


@router.post("/predict/asset-risk")
def predict_asset_risk(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = asset_adapter.predict(payload)
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
    return {**result, "persisted_id": persisted_id, "disclaimer": "ML prediction only — does not approve block"}


@router.post("/predict/maintenance-duration")
def predict_duration(payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    maintenance_request_id = payload.pop("maintenance_request_id", None)
    if maintenance_request_id:
        _check_request_access(db, current_user, maintenance_request_id)
    try:
        result = duration_adapter.predict(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    persisted_id = None
    if maintenance_request_id:
        mp = persist_prediction(db, maintenance_request_id, result, current_user.id)
        persisted_id = mp.id
    else:
        log = AuditLog(user_id=current_user.id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=None, description=f"DEMO duration {result['model_version']}")
        db.add(log)
        db.commit()
    return {**result, "persisted_id": persisted_id, "disclaimer": "DEMO/SYNTHETIC — NOT FOR PRODUCTION, genuine model not yet supplied. ML never approves."}


@router.post("/predict/maintenance-request/{request_id}")
def predict_for_request(request_id: int, payload: Dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Unified endpoint: payload contains optional train_impact_features, asset_risk_features, duration_features."""
    req = _check_request_access(db, current_user, request_id)
    ensure_registry(db)
    results = {}
    persisted = []

    if "train_impact" in payload:
        try:
            ti = train_adapter.predict(payload["train_impact"])
            mp = persist_prediction(db, request_id, ti, current_user.id)
            results["train_impact"] = {**ti, "persisted_id": mp.id}
            persisted.append(mp.id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"train_impact: {e}")

    if "asset_risk" in payload:
        try:
            ar = asset_adapter.predict(payload["asset_risk"])
            mp = persist_prediction(db, request_id, ar, current_user.id)
            results["asset_risk"] = {**ar, "persisted_id": mp.id}
            persisted.append(mp.id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"asset_risk: {e}")

    if "maintenance_duration" in payload:
        try:
            md = duration_adapter.predict(payload["maintenance_duration"])
            mp = persist_prediction(db, request_id, md, current_user.id)
            results["maintenance_duration"] = {**md, "persisted_id": mp.id}
            persisted.append(mp.id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"maintenance_duration: {e}")

    if not results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one of train_impact, asset_risk, maintenance_duration")

    return {"request_id": request_id, "results": results, "disclaimer": "ML predicts only — Safety/OR-Tools/Official required"}


@router.get("/predictions/{request_id}")
def get_predictions(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    req = _check_request_access(db, current_user, request_id)
    from app.models.maintenance import MaintenancePrediction

    rows = db.query(MaintenancePrediction).filter(MaintenancePrediction.maintenance_request_id == request_id).order_by(MaintenancePrediction.predicted_at.desc()).all()
    return [
        {
            "id": r.id,
            "maintenance_request_id": r.maintenance_request_id,
            "asset_risk_score": float(r.asset_risk_score) if r.asset_risk_score is not None else None,
            "risk_level": r.risk_level,
            "predicted_duration_mins": r.predicted_duration_mins,
            "train_impact_score": float(r.train_impact_score) if r.train_impact_score is not None else None,
            "predicted_delay_mins": r.predicted_delay_mins,
            "affected_train_count": r.affected_train_count,
            "model_version": r.model_version,
            "input_features": r.input_features,
            "predicted_at": r.predicted_at,
        }
        for r in rows
    ]
