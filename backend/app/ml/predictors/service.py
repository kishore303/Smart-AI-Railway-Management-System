from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.models.maintenance import MaintenancePrediction, MlModelRegistry
from app.models.audit import AuditLog


def ensure_registry(db: Session):
    """Seed ml_model_registry if empty — reflects actual artifacts."""
    if db.query(MlModelRegistry).count() > 0:
        return
    entries = [
        {"model_type": "TRAIN_IMPACT", "version": "train_impact_v1_sklearn1.6.1_RF100", "artifact_filename": "etrain_delay_model_pipeline.joblib", "is_demo": False, "is_active": True, "notes": "Verified 8 features, RF100"},
        {"model_type": "ASSET_RISK", "version": "asset_risk_v1_sklearn1.6.1_RF100", "artifact_filename": "railway_maintenance_model_pipeline.joblib", "is_demo": False, "is_active": True, "notes": "31 features, RF classifier"},
        {"model_type": "MAINTENANCE_DURATION", "version": "maintenance_duration_DEMO_v1_synthetic", "artifact_filename": "maintenance_data.joblib (DATASET)", "is_demo": True, "is_active": True, "notes": "DEMO/SYNTHETIC — genuine model not yet supplied, 5000-row dataset"},
    ]
    for e in entries:
        r = MlModelRegistry(**e)
        db.add(r)
    db.commit()


def persist_prediction(db: Session, maintenance_request_id: int, result: Dict[str, Any], user_id: Optional[int] = None) -> MaintenancePrediction:
    """Persist to maintenance_predictions per authoritative schema. result must contain input_features."""
    # Map adapter result to DB columns
    mp = MaintenancePrediction(
        maintenance_request_id=maintenance_request_id,
        asset_risk_score=result.get("asset_risk_score"),
        risk_level=result.get("risk_level"),
        predicted_duration_mins=result.get("predicted_duration_mins"),
        train_impact_score=result.get("train_impact_score"),
        predicted_delay_mins=result.get("predicted_delay_mins"),
        affected_train_count=result.get("affected_train_count"),
        model_version=result.get("model_version"),
        input_features=result.get("input_features"),
    )
    db.add(mp)
    db.commit()
    db.refresh(mp)
    # Audit
    if user_id:
        log = AuditLog(user_id=user_id, action="RUN_PREDICTION", entity_type="maintenance_request", entity_id=maintenance_request_id, description=f"ML {result.get('model_version')} is_demo={result.get('is_demo')} delay={result.get('predicted_delay_mins')} risk={result.get('asset_risk_score')}")
        db.add(log)
        db.commit()
    return mp
