"""Unified ML Prediction Service.

Orchestrates:
1. Maintenance Duration Prediction (maintenance_duration_model.joblib)
2. Operational / Asset Risk Prediction (railway_maintenance_model_pipeline.joblib)
3. Timetable Train Impact Analysis & Delay Prediction (TrainScheduleService + etrain_delay_model_pipeline.joblib)

Handles database entity extraction, feature snapshotting, persistence into maintenance_predictions,
audit logging, and stale prediction detection.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.maintenance import MaintenanceRequest, MaintenancePrediction
from app.models.asset import Asset
from app.models.department import Department
from app.models.audit import AuditLog
from app.ml.predictors.maintenance_duration import MaintenanceDurationPredictor
from app.ml.predictors.risk import AssetRiskPredictor
from app.services.train_impact import TrainImpactService
from app.ml.predictors.service import ensure_registry


class MLPredictionService:
    """Unified service providing all prediction capabilities for maintenance requests and standalone queries."""

    def __init__(self):
        self.duration_predictor = MaintenanceDurationPredictor()
        self.risk_predictor = AssetRiskPredictor()
        self.train_impact_service = TrainImpactService()

    def is_prediction_stale(self, req: MaintenanceRequest, latest_pred: Optional[MaintenancePrediction]) -> bool:
        """Check if a stored prediction is stale due to request updates after prediction was generated."""
        if not latest_pred:
            return True
        if req.updated_at and req.updated_at > latest_pred.predicted_at:
            return True
        return False

    def predict_for_maintenance_request(
        self,
        db: Session,
        maintenance_request_id: int,
        user_id: Optional[int] = None,
        custom_inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full unified prediction pipeline for a verified maintenance request.
        Persists structured record to maintenance_predictions and creates audit log.
        """
        ensure_registry(db)

        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == maintenance_request_id).first()
        if not req:
            raise ValueError(f"Maintenance request #{maintenance_request_id} not found")

        asset = db.query(Asset).filter(Asset.id == req.asset_id).first() if req.asset_id else None
        dept = db.query(Department).filter(Department.id == req.department_id).first() if req.department_id else None

        dept_name = dept.name if dept else "Engineering"
        asset_type = asset.asset_type if asset and hasattr(asset, "asset_type") else "Track"
        asset_age = 5
        condition_score = float(asset.condition_score) if asset and asset.condition_score is not None else 80.0

        custom = custom_inputs or {}

        # 1. Prepare & Predict Maintenance Duration
        duration_input = {
            "maintenance_type": req.maintenance_type,
            "department": dept_name,
            "asset_type": asset_type,
            "complexity": custom.get("complexity", "Medium"),
            "priority": req.priority,
            "workers": custom.get("workers", 6),
            "equipment_count": custom.get("equipment_count", 2),
            "asset_age_years": custom.get("asset_age_years", asset_age),
            "condition_score": custom.get("condition_score", condition_score),
            "previous_duration_min": req.requested_duration_mins or 120,
        }
        duration_res = self.duration_predictor.predict(duration_input, allow_defaults=True)

        # 2. Prepare & Predict Operational Risk
        risk_input = {
            "region": custom.get("region", "Northern"),
            "season": custom.get("season", "Summer"),
            "train_type": custom.get("train_type", "Express"),
            "ballast_condition": custom.get("ballast_condition", "Good"),
            "signal_system_status": custom.get("signal_system_status", "Normal"),
            "rail_wear_mm": custom.get("rail_wear_mm", 2.2),
            "track_temperature_c": custom.get("track_temperature_c", 32.0),
            "ambient_temperature_c": custom.get("ambient_temperature_c", 29.0),
            "humidity_percent": custom.get("humidity_percent", 55.0),
            "inspection_score": custom.get("inspection_score", 85.0),
            "sensor_health_index": custom.get("sensor_health_index", 90.0),
        }
        risk_res = self.risk_predictor.predict(risk_input, allow_defaults=True)

        # 3. Timetable & Train Impact Analysis
        train_impact_res = self.train_impact_service.assess_train_impact(
            db=db,
            section_id=req.section_id,
            track_id=req.track_id,
            start_time=req.requested_start,
            end_time=req.requested_end,
        )

        # Combined feature snapshot
        combined_features = {
            "duration_features": duration_res.get("input_features", {}),
            "risk_features": risk_res.get("input_features", {}),
            "section_id": req.section_id,
            "track_id": req.track_id,
            "requested_start": req.requested_start.isoformat() if req.requested_start else None,
            "requested_end": req.requested_end.isoformat() if req.requested_end else None,
        }

        # 4. Persist to maintenance_predictions
        mp = MaintenancePrediction(
            maintenance_request_id=req.id,
            asset_risk_score=risk_res["asset_risk_score"],
            risk_level=risk_res["risk_level"],
            predicted_duration_mins=duration_res["predicted_duration_mins"],
            train_impact_score=train_impact_res.get("train_impact_score", 0.0),
            predicted_delay_mins=int(round(train_impact_res.get("total_predicted_delay_minutes", 0.0))),
            affected_train_count=train_impact_res.get("affected_train_count", 0),
            model_version=f"{duration_res['model_version']}|{risk_res['model_version']}|{train_impact_res.get('model_version', 'v1')}"[:250],
            input_features=combined_features,
            predicted_at=datetime.now(timezone.utc),
        )
        db.add(mp)
        db.commit()
        db.refresh(mp)

        # 5. Audit Logging
        if user_id:
            audit = AuditLog(
                user_id=user_id,
                action="RUN_PREDICTION",
                entity_type="MaintenancePrediction",
                entity_id=mp.id,
                description=(
                    f"AI Prediction: Duration={duration_res['predicted_duration_mins']}m, "
                    f"Risk={risk_res['risk_level']}({risk_res['risk_probability']*100:.1f}%), "
                    f"Trains={train_impact_res.get('affected_train_count', 0)}, Delay={train_impact_res.get('total_predicted_delay_minutes', 0.0)}m"
                ),
            )
            db.add(audit)
            db.commit()

        out_duration = {
            "predicted_duration_minutes": duration_res["predicted_duration_minutes"],
            "predicted_duration_mins": duration_res["predicted_duration_mins"],
            "confidence_interval_lower_mins": duration_res.get("confidence_interval_lower_mins"),
            "confidence_interval_upper_mins": duration_res.get("confidence_interval_upper_mins"),
            "model_name": duration_res["model_name"],
            "model_version": duration_res["model_version"],
        }

        out_risk = {
            "risk_class": risk_res["risk_class"],
            "risk_probability": risk_res["risk_probability"],
            "asset_risk_score": risk_res["asset_risk_score"],
            "risk_level": risk_res["risk_level"],
            "model_name": risk_res["model_name"],
            "model_version": risk_res["model_version"],
        }

        return {
            "status": "COMPLETED",
            "prediction_id": mp.id,
            "maintenance_request_id": req.id,
            "is_stale": False,
            "is_demo": False,
            "predicted_at": mp.predicted_at.isoformat(),
            "duration": out_duration,
            "duration_prediction": out_duration,
            "risk": out_risk,
            "risk_prediction": out_risk,
            "train_impact": train_impact_res,
            "disclaimer": "AI/ML prediction outputs are decision support metrics only. Deterministic Safety Engine validation and Railway Official authorization are required for block execution.",
        }
