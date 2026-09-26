"""Asset / Operational Risk Predictor Service.

Uses railway_maintenance_model_pipeline.joblib (RandomForestClassifier Pipeline).
Predicts operational risk class (0/1) and risk probability.
"""
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime, timezone
from app.ml.loaders import load_asset_risk


class AssetRiskPredictor:
    """Predicts operational and railway risk using railway_maintenance_model_pipeline."""

    NUMERIC_COLUMNS = [
        "train_age_years",
        "average_speed_kmph",
        "distance_travelled_km",
        "track_temperature_c",
        "rail_wear_mm",
        "track_vibration_level",
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
        "power_consumption_kw",
        "load_factor_percent",
        "daily_trips",
        "delay_minutes",
        "last_maintenance_days",
        "inspection_score",
        "sensor_health_index",
        "risk_score",
    ]

    CATEGORICAL_COLUMNS = [
        "region",
        "season",
        "train_type",
        "ballast_condition",
        "signal_system_status",
    ]

    ALL_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS

    DEFAULT_VALUES = {
        "train_age_years": 8.0,
        "average_speed_kmph": 75.0,
        "distance_travelled_km": 1500.0,
        "track_temperature_c": 32.0,
        "rail_wear_mm": 2.5,
        "track_vibration_level": 1.5,
        "track_curvature_degree": 1.2,
        "ambient_temperature_c": 28.0,
        "humidity_percent": 60.0,
        "rainfall_mm": 0.0,
        "wind_speed_kmph": 12.0,
        "wheel_wear_percent": 25.0,
        "axle_temperature_c": 50.0,
        "brake_pressure_psi": 72.0,
        "brake_pad_wear_percent": 35.0,
        "bearing_temperature_c": 55.0,
        "battery_voltage": 24.0,
        "traction_motor_temp_c": 60.0,
        "power_consumption_kw": 320.0,
        "load_factor_percent": 70.0,
        "daily_trips": 4.0,
        "delay_minutes": 5.0,
        "last_maintenance_days": 20.0,
        "inspection_score": 85.0,
        "sensor_health_index": 90.0,
        "risk_score": 30.0,
        "region": "Northern",
        "season": "Summer",
        "train_type": "Express",
        "ballast_condition": "Good",
        "signal_system_status": "Normal",
    }

    def __init__(self):
        self.model_name = "railway_maintenance_model_pipeline"
        self.model_version = "asset_risk_v1_sklearn1.6.1_RF100"

    def validate_features(self, data: Dict[str, Any], allow_defaults: bool = True) -> pd.DataFrame:
        """Validate and adapt input dictionary into DataFrame matching exact model pipeline schema."""
        row: Dict[str, Any] = {}
        for col in self.NUMERIC_COLUMNS:
            if col in data and data[col] is not None:
                try:
                    row[col] = float(data[col])
                except (ValueError, TypeError):
                    raise ValueError(f"Numeric feature '{col}' has invalid value: {data[col]}")
            elif allow_defaults and col in self.DEFAULT_VALUES:
                row[col] = float(self.DEFAULT_VALUES[col])
            else:
                raise ValueError(f"Missing required numeric feature for risk model: '{col}'")

        for col in self.CATEGORICAL_COLUMNS:
            if col in data and data[col] is not None:
                row[col] = str(data[col]).strip()
            elif allow_defaults and col in self.DEFAULT_VALUES:
                row[col] = str(self.DEFAULT_VALUES[col])
            else:
                raise ValueError(f"Missing required categorical feature for risk model: '{col}'")

        return pd.DataFrame([row])

    def predict(self, data: Dict[str, Any], allow_defaults: bool = True) -> Dict[str, Any]:
        """Perform operational risk classification and probability prediction."""
        df_input = self.validate_features(data, allow_defaults=allow_defaults)
        pipeline = load_asset_risk()
        
        raw_pred = pipeline.predict(df_input)
        raw_proba = pipeline.predict_proba(df_input)

        predicted_class = int(raw_pred[0])
        # Probability for Class 1 (High/Elevated Risk)
        prob_high = float(raw_proba[0][1]) if len(raw_proba[0]) > 1 else float(predicted_class)

        # Map to railway qualitative severity level
        if prob_high < 0.25:
            risk_level = "LOW"
        elif prob_high < 0.50:
            risk_level = "MEDIUM"
        elif prob_high < 0.75:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return {
            "status": "SUCCESS",
            "model_name": self.model_name,
            "model_version": self.model_version,
            "predicted_class": predicted_class,
            "risk_class": predicted_class,
            "risk_probability": round(prob_high, 4),
            "asset_risk_score": round(prob_high, 3),
            "risk_level": risk_level,
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_features": df_input.iloc[0].to_dict(),
        }
