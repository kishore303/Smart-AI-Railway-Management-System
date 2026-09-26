"""Maintenance Duration Predictor Service.

Uses maintenance_duration_model.joblib (RandomForestRegressor Pipeline trained on maintenance_data.joblib).
Predicts expected maintenance duration in minutes.
"""
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime, timezone
from app.ml.loaders import load_maintenance_duration_model


class MaintenanceDurationPredictor:
    """Predicts maintenance duration in minutes using maintenance_duration_model."""

    CATEGORICAL_COLUMNS = [
        "maintenance_type",
        "department",
        "asset_type",
        "complexity",
        "priority",
    ]

    NUMERIC_COLUMNS = [
        "workers",
        "equipment_count",
        "asset_age_years",
        "condition_score",
        "previous_duration_min",
    ]

    ALL_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS

    DEFAULT_VALUES = {
        "maintenance_type": "Track Inspection",
        "department": "Engineering",
        "asset_type": "Track",
        "complexity": "Medium",
        "priority": "MEDIUM",
        "workers": 6,
        "equipment_count": 2,
        "asset_age_years": 7,
        "condition_score": 75.0,
        "previous_duration_min": 120,
    }

    def __init__(self):
        self.model_name = "maintenance_duration_model"
        self.model_version = "maintenance_duration_v1_RF100_R2_0.82"

    def validate_features(self, data: Dict[str, Any], allow_defaults: bool = True) -> pd.DataFrame:
        """Validate input dictionary and adapt to DataFrame matching model schema."""
        row: Dict[str, Any] = {}
        for col in self.CATEGORICAL_COLUMNS:
            if col in data and data[col] is not None:
                row[col] = str(data[col]).strip()
            elif allow_defaults and col in self.DEFAULT_VALUES:
                row[col] = str(self.DEFAULT_VALUES[col])
            else:
                raise ValueError(f"Missing required categorical feature for maintenance duration model: '{col}'")

        for col in self.NUMERIC_COLUMNS:
            if col in data and data[col] is not None:
                try:
                    row[col] = float(data[col]) if col == "condition_score" else int(data[col])
                except (ValueError, TypeError):
                    raise ValueError(f"Numeric feature '{col}' has invalid value: {data[col]}")
            elif allow_defaults and col in self.DEFAULT_VALUES:
                row[col] = self.DEFAULT_VALUES[col]
            else:
                raise ValueError(f"Missing required numeric feature for maintenance duration model: '{col}'")

        # Sanity checks on physical bounds
        if row["workers"] < 1 or row["workers"] > 500:
            raise ValueError(f"Workers count ({row['workers']}) must be between 1 and 500")
        if row["equipment_count"] < 0 or row["equipment_count"] > 100:
            raise ValueError(f"Equipment count ({row['equipment_count']}) must be between 0 and 100")

        return pd.DataFrame([row])

    def predict(self, data: Dict[str, Any], allow_defaults: bool = True) -> Dict[str, Any]:
        """Perform maintenance duration prediction."""
        df_input = self.validate_features(data, allow_defaults=allow_defaults)
        pipeline = load_maintenance_duration_model()
        raw_pred = pipeline.predict(df_input)
        duration_mins = max(15.0, float(raw_pred[0]))
        pred_int = int(round(duration_mins))
        ci_lower = max(15, pred_int - 35)
        ci_upper = pred_int + 35

        return {
            "status": "SUCCESS",
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_type": "RandomForestRegressor",
            "predicted_duration_minutes": round(duration_mins, 1),
            "predicted_duration_mins": pred_int,
            "confidence_interval_lower_mins": ci_lower,
            "confidence_interval_upper_mins": ci_upper,
            "is_demo": False,
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_features": df_input.iloc[0].to_dict(),
        }
