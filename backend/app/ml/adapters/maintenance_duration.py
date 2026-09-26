from typing import Any, Dict
import random

from app.ml.adapters.base import BasePredictor
from app.ml.loaders import load_maintenance_data

# This adapter is intentionally DEMO/SYNTHETIC — genuine model not supplied
# maintenance_data.joblib is a DataFrame, not a Pipeline with predict()


class MaintenanceDurationDemoAdapter(BasePredictor):
    @property
    def model_type(self) -> str:
        return "MAINTENANCE_DURATION"

    @property
    def is_demo(self) -> bool:
        return True

    @property
    def artifact_filename(self) -> str:
        return "maintenance_data.joblib (DATASET — no trained model)"

    @property
    def version(self) -> str:
        return "maintenance_duration_DEMO_v1_synthetic"

    def validate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        # Minimal required for demo estimation
        required = ["maintenance_type", "priority", "workers", "equipment_count"]
        missing = [f for f in required if f not in features]
        if missing:
            raise ValueError(f"Missing required fields for DEMO duration: {missing}")
        # Validate priority
        if features["priority"] not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("priority must be LOW/MEDIUM/HIGH/CRITICAL")
        try:
            w = int(features["workers"])
            if not (1 <= w <= 100):
                raise ValueError("workers 1-100")
        except Exception:
            raise ValueError("workers must be integer 1-100")
        try:
            e = int(features["equipment_count"])
            if not (0 <= e <= 50):
                raise ValueError("equipment_count 0-50")
        except Exception:
            raise ValueError("equipment_count must be integer 0-50")
        return features

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        clean = self.validate(features)
        # Guard: ensure dataset not used as model
        data = load_maintenance_data()  # DataFrame load, but we don't call predict on it
        # Synthetic heuristic: base duration by maintenance_type complexity
        base_map = {"Track": 90, "OHE": 75, "Signal": 60, "Electrical": 80, "Bridge": 120}
        mtype = str(clean.get("maintenance_type", "Track"))
        base = 60
        for k, v in base_map.items():
            if k.lower() in mtype.lower():
                base = v
                break
        priority_mult = {"LOW": 0.8, "MEDIUM": 1.0, "HIGH": 1.2, "CRITICAL": 1.5}[clean["priority"]]
        # Workers reduce time, equipment slight
        workers = int(clean["workers"])
        # Deterministic variation
        variation = (hash(f"{clean['maintenance_type']}_{workers}_{clean['equipment_count']}") % 11) - 5
        duration = base * priority_mult * (1 - min(workers - 1, 10) * 0.03) + variation
        duration = max(15, int(round(duration)))
        return {
            "predicted_duration_mins": duration,
            "model_version": self.version,
            "artifact_filename": self.artifact_filename,
            "is_demo": True,
            "demo_label": "DEMO/SYNTHETIC — NOT FOR PRODUCTION, genuine maintenance-duration model not yet supplied",
            "input_features": clean,
            "dataset_rows": int(data.shape[0]) if hasattr(data, "shape") else None,
            "dataset_columns": list(data.columns) if hasattr(data, "columns") else None,
        }
