"""Train Delay Predictor Service.

Uses etrain_delay_model_pipeline.joblib (RandomForestRegressor Pipeline).
Predicts train delay in minutes for an individual train.
"""
from typing import Dict, Any, Union
import pandas as pd
from datetime import datetime, timezone
from app.ml.loaders import load_train_impact


class TrainDelayPredictor:
    """Predicts train delay in minutes using etrain_delay_model_pipeline."""

    NUMERIC_COLUMNS = [
        "train_number",
        "pct_right_time",
        "pct_slight_delay",
        "pct_significant_delay",
        "pct_cancelled_unknown",
    ]
    CATEGORICAL_COLUMNS = [
        "train_name",
        "station_code",
        "station_name",
    ]
    ALL_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS

    def __init__(self):
        self.model_name = "etrain_delay_model_pipeline"
        self.model_version = "train_impact_v1_sklearn1.6.1_RF100"

    def validate_features(self, data: Dict[str, Any]) -> pd.DataFrame:
        """Validate input features and prepare DataFrame in exact model schema."""
        missing = [c for c in self.ALL_COLUMNS if c not in data]
        if missing:
            raise ValueError(f"Missing required features for train delay model: {missing}")

        row: Dict[str, Any] = {}
        for col in self.NUMERIC_COLUMNS:
            val = data[col]
            try:
                row[col] = float(val) if col != "train_number" else int(val)
            except (ValueError, TypeError):
                raise ValueError(f"Feature '{col}' must be numeric, got: {val}")

        for col in self.CATEGORICAL_COLUMNS:
            row[col] = str(data[col]).strip()

        # Validate percentage sum sanity (should be roughly ~100%)
        pct_sum = (
            row["pct_right_time"]
            + row["pct_slight_delay"]
            + row["pct_significant_delay"]
            + row["pct_cancelled_unknown"]
        )
        if pct_sum < 50.0 or pct_sum > 150.0:
            raise ValueError(f"Sum of performance percentages ({pct_sum:.1f}%) is outside valid range (50-150%)")

        return pd.DataFrame([row])

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform train delay prediction for a single train record."""
        df_input = self.validate_features(data)
        pipeline = load_train_impact()
        raw_pred = pipeline.predict(df_input)
        delay_mins = max(0.0, float(raw_pred[0]))

        # Calculate qualitative impact level
        if delay_mins < 10.0:
            impact_level = "LOW"
            impact_score = 0.2
        elif delay_mins < 30.0:
            impact_level = "MEDIUM"
            impact_score = 0.5
        elif delay_mins < 60.0:
            impact_level = "HIGH"
            impact_score = 0.8
        else:
            impact_level = "CRITICAL"
            impact_score = 1.0

        return {
            "status": "SUCCESS",
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_type": "RandomForestRegressor",
            "is_demo": False,
            "predicted_delay_mins": round(delay_mins, 2),
            "predicted_delay_minutes": round(delay_mins, 2),
            "train_impact_score": impact_score,
            "impact_level": impact_level,
            "affected_train_count": 1,
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_features": data,
        }
