import hashlib
import joblib
from pathlib import Path
from typing import Any

# Centralized loaders with sklearn 1.6.1 compatibility shim
# Preserves exact MD5/hash of supplied artifacts — no retraining

_ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "model_artifacts"

# Expected MD5s (verified from Module 1/VERIFIED)
EXPECTED_MD5 = {
    "train_impact": "6b04723260427bc891736b7ce74adf93",
    "asset_risk": "3914c6e942b7b3eecfd7ed5481fc5b57",
    "maintenance_duration_data": "bc501e69d592932aad487d0a4909675c",
}

_cache: dict[str, Any] = {}


def _ensure_shim():
    try:
        import sklearn.compose._column_transformer as ct

        if not hasattr(ct, "_RemainderColsList"):
            class _RemainderColsList(list):
                pass

            ct._RemainderColsList = _RemainderColsList
    except Exception:
        pass


def md5_of_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_md5(path: Path, expected: str) -> bool:
    if not path.exists():
        return False
    return md5_of_file(path) == expected


def load_train_impact():
    """Load train_impact etrain_delay_model_pipeline.joblib — genuine Pipeline."""
    key = "train_impact"
    if key in _cache:
        return _cache[key]
    _ensure_shim()
    p = _ARTIFACT_ROOT / "train_impact" / "etrain_delay_model_pipeline.joblib"
    if not p.exists():
        raise FileNotFoundError(f"Train impact artifact not found at {p}")
    if not verify_md5(p, EXPECTED_MD5["train_impact"]):
        raise ValueError(f"MD5 mismatch for {p}: expected {EXPECTED_MD5['train_impact']}, got {md5_of_file(p)} — artifact may have been modified")
    obj = joblib.load(p)
    _cache[key] = obj
    return obj


def load_asset_risk():
    key = "asset_risk"
    if key in _cache:
        return _cache[key]
    _ensure_shim()
    p = _ARTIFACT_ROOT / "asset_risk" / "railway_maintenance_model_pipeline.joblib"
    if not p.exists():
        raise FileNotFoundError(f"Asset risk artifact not found at {p}")
    if not verify_md5(p, EXPECTED_MD5["asset_risk"]):
        raise ValueError(f"MD5 mismatch for {p}")
    obj = joblib.load(p)
    _cache[key] = obj
    return obj


def load_maintenance_data():
    """Load maintenance_data.joblib — DataFrame, NOT a model."""
    key = "maintenance_duration_data"
    if key in _cache:
        return _cache[key]
    p = _ARTIFACT_ROOT / "maintenance_duration" / "maintenance_data.joblib"
    if not p.exists():
        raise FileNotFoundError(f"Maintenance data not found at {p}")
    if not verify_md5(p, EXPECTED_MD5["maintenance_duration_data"]):
        raise ValueError(f"MD5 mismatch for {p}")
    obj = joblib.load(p)
    # Guard: must be DataFrame, not Pipeline
    if hasattr(obj, "predict"):
        raise TypeError("maintenance_data.joblib has predict() — unexpected, should be DataFrame")
    _cache[key] = obj
    return obj


def clear_cache():
    _cache.clear()


def model_info(key: str) -> dict:
    path_map = {
        "train_impact": _ARTIFACT_ROOT / "train_impact" / "etrain_delay_model_pipeline.joblib",
        "asset_risk": _ARTIFACT_ROOT / "asset_risk" / "railway_maintenance_model_pipeline.joblib",
        "maintenance_duration_data": _ARTIFACT_ROOT / "maintenance_duration" / "maintenance_data.joblib",
    }
    p = path_map.get(key)
    if not p or not p.exists():
        return {"exists": False, "path": str(p) if p else None}
    return {
        "exists": True,
        "path": str(p),
        "md5": md5_of_file(p),
        "expected_md5": EXPECTED_MD5.get(key),
        "verified": verify_md5(p, EXPECTED_MD5.get(key, "")),
        "size": p.stat().st_size,
    }
