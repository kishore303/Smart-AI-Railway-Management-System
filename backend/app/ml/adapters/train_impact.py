import pandas as pd
from typing import Any, Dict

from app.ml.adapters.base import BasePredictor
from app.ml.loaders import load_train_impact

# Verified 8-feature schema from master prompt Section 16
NUMERIC_FEATURES = [
    "train_number",
    "pct_right_time",
    "pct_slight_delay",
    "pct_significant_delay",
    "pct_cancelled_unknown",
]
CATEGORICAL_FEATURES = [
    "train_name",
    "station_code",
    "station_name",
]
ALL_FEATURES = [
    "train_number",
    "train_name",
    "station_code",
    "station_name",
    "pct_right_time",
    "pct_slight_delay",
    "pct_significant_delay",
    "pct_cancelled_unknown",
]


class TrainImpactAdapter(BasePredictor):
    @property
    def model_type(self) -> str:
        return "TRAIN_IMPACT"

    @property
    def artifact_filename(self) -> str:
        return "etrain_delay_model_pipeline.joblib"

    @property
    def version(self) -> str:
        return "train_impact_v1_sklearn1.6.1_RF100"

    def validate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        missing = [f for f in ALL_FEATURES if f not in features]
        if missing:
            raise ValueError(f"Missing required features: {missing}. Required 8: {ALL_FEATURES}")
        extra = [k for k in features if k not in ALL_FEATURES]
        if extra:
            raise ValueError(f"Unexpected features {extra}. Allowed: {ALL_FEATURES}")

        out = {}
        # train_number: int positive
        try:
            tn = int(features["train_number"])
        except Exception:
            raise ValueError("train_number must be integer")
        if tn <= 0:
            raise ValueError("train_number must be >0")
        out["train_number"] = tn

        # categorical: non-empty string
        for f in CATEGORICAL_FEATURES:
            v = features[f]
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"{f} must be non-empty string")
            out[f] = v.strip()

        # numeric pct: 0-100
        for f in NUMERIC_FEATURES:
            if f == "train_number":
                continue
            try:
                v = float(features[f])
            except Exception:
                raise ValueError(f"{f} must be numeric")
            if not (0 <= v <= 100):
                raise ValueError(f"{f} must be 0-100, got {v}")
            out[f] = v

        # pct sum sanity (should be ~100±2)
        pct_sum = out["pct_right_time"] + out["pct_slight_delay"] + out["pct_significant_delay"] + out["pct_cancelled_unknown"]
        if not (98 <= pct_sum <= 102):
            raise ValueError(f"pct_* fields should sum ~100, got {pct_sum}")

        return out

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        clean = self.validate(features)
        model = load_train_impact()
        # model expects DataFrame with 8 cols
        df = pd.DataFrame([clean], columns=ALL_FEATURES)
        # Ensure dtypes: train_number int, pct floats, categorical str
        pred = model.predict(df)
        delay = float(pred[0])
        # Clamp to non-negative
        delay = max(0.0, delay)
        # Heuristic affected_train_count and impact level from delay
        # Real model only predicts delay; we derive level for storage
        if delay < 15:
            level = "LOW"
        elif delay < 30:
            level = "MEDIUM"
        elif delay < 60:
            level = "HIGH"
        else:
            level = "CRITICAL"
        return {
            "predicted_delay_mins": int(round(delay)),
            "train_impact_score": round(delay / 10, 3),  # synthetic score for maintenance_predictions
            "affected_train_count": 1,  # per-input single train
            "impact_level": level,
            "model_version": self.version,
            "artifact_filename": self.artifact_filename,
            "is_demo": False,
            "input_features": clean,
        }
