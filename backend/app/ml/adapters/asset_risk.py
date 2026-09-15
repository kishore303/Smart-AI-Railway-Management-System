import pandas as pd
from typing import Any, Dict

from app.ml.adapters.base import BasePredictor
from app.ml.loaders import load_asset_risk

# 31-feature schema extracted from actual pipeline feature_names_in_
ALL_FEATURES = [
    "region",
    "season",
    "train_type",
    "train_age_years",
    "average_speed_kmph",
    "distance_travelled_km",
    "track_temperature_c",
    "rail_wear_mm",
    "track_vibration_level",
    "ballast_condition",
    "track_curvature_degree",
    "ambient_temperature_c",
    "humidity_percent",
    "rainfall_mm",
    "wind_speed_kmph",
    "wheel_wear_percent",
    "axle_temperature_c",
    "brake_pressure_psi",
    "brake_pad_wear_percent",
    "bearing_temperature_c",
    "battery_voltage",
    "traction_motor_temp_c",
    "signal_system_status",
    "power_consumption_kw",
    "load_factor_percent",
    "daily_trips",
    "delay_minutes",
    "last_maintenance_days",
    "inspection_score",
    "sensor_health_index",
    "risk_score",
]

CATEGORICAL = {
    "region": {"North", "South", "East", "West", "Central", "North-East"},
    "season": {"Summer", "Monsoon", "Winter"},
    "train_type": {"Express", "Freight", "Passenger", "Local"},
    "ballast_condition": {"Good", "Average", "Poor"},
    "signal_system_status": {"Normal", "Warning", "Failed"},
}

# Numeric ranges for strict validation (based on training data expectations)
RANGES = {
    "train_age_years": (0, 50),
    "average_speed_kmph": (0, 200),
    "distance_travelled_km": (0, 50000),
    "track_temperature_c": (-10, 80),
    "rail_wear_mm": (0, 20),
    "track_vibration_level": (0, 10),
    "track_curvature_degree": (0, 15),
    "ambient_temperature_c": (-10, 60),
    "humidity_percent": (0, 100),
    "rainfall_mm": (0, 500),
    "wind_speed_kmph": (0, 150),
    "wheel_wear_percent": (0, 100),
    "axle_temperature_c": (-10, 150),
    "brake_pressure_psi": (0, 150),
    "brake_pad_wear_percent": (0, 100),
    "bearing_temperature_c": (-10, 150),
    "battery_voltage": (0, 200),
    "traction_motor_temp_c": (-10, 200),
    "power_consumption_kw": (0, 10000),
    "load_factor_percent": (0, 100),
    "daily_trips": (0, 20),
    "delay_minutes": (0, 1440),
    "last_maintenance_days": (0, 3650),
    "inspection_score": (0, 100),
    "sensor_health_index": (0, 100),
    "risk_score": (0, 1),
}


class AssetRiskAdapter(BasePredictor):
    @property
    def model_type(self) -> str:
        return "ASSET_RISK"

    @property
    def artifact_filename(self) -> str:
        return "railway_maintenance_model_pipeline.joblib"

    @property
    def version(self) -> str:
        return "asset_risk_v1_sklearn1.6.1_RF100"

    def validate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        missing = [f for f in ALL_FEATURES if f not in features]
        if missing:
            raise ValueError(f"Missing required Asset Risk features: {missing}. Required 31: {ALL_FEATURES}")
        extra = [k for k in features if k not in ALL_FEATURES]
        if extra:
            raise ValueError(f"Unexpected features {extra}. Allowed 31: {ALL_FEATURES}")

        out: Dict[str, Any] = {}
        for f in ALL_FEATURES:
            v = features[f]
            if f in CATEGORICAL:
                if not isinstance(v, str) or not v.strip():
                    raise ValueError(f"{f} must be non-empty string")
                vs = v.strip()
                # Strict categorical check — if not in known set, still allow but warn via error for safety
                # We enforce membership to avoid silent drift
                if vs not in CATEGORICAL[f]:
                    raise ValueError(f"{f} invalid value '{vs}'. Allowed {sorted(CATEGORICAL[f])}")
                out[f] = vs
            else:
                try:
                    fv = float(v)
                except Exception:
                    raise ValueError(f"{f} must be numeric, got {v}")
                lo, hi = RANGES.get(f, (None, None))
                if lo is not None and not (lo <= fv <= hi):
                    raise ValueError(f"{f} out of range [{lo},{hi}], got {fv}")
                out[f] = fv
        return out

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        clean = self.validate(features)
        model = load_asset_risk()
        df = pd.DataFrame([clean], columns=ALL_FEATURES)
        # Classifier predicts 0/1
        proba = None
        pred = model.predict(df)[0]
        try:
            proba = model.predict_proba(df)[0]
            # proba[1] is risk prob
            risk_score = float(proba[1])
        except Exception:
            risk_score = float(pred)
        # Map to risk level
        if risk_score < 0.3:
            level = "LOW"
        elif risk_score < 0.6:
            level = "MEDIUM"
        elif risk_score < 0.85:
            level = "HIGH"
        else:
            level = "CRITICAL"
        return {
            "asset_risk_score": round(float(risk_score), 3),
            "risk_level": level,
            "predicted_class": int(pred),
            "model_version": self.version,
            "artifact_filename": self.artifact_filename,
            "is_demo": False,
            "input_features": clean,
        }
