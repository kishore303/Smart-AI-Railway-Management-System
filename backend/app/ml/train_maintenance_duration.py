"""Training script for Maintenance Duration Prediction Model.

Dataset: maintenance_data.joblib (5,000 records)
Architecture:
- Categorical preprocessing via OneHotEncoder (handle_unknown='ignore')
- Numerical preprocessing via StandardScaler
- Estimator: RandomForestRegressor(n_estimators=100, random_state=42)
- Target: maintenance_duration_minutes

Saves pipeline artifact to:
backend/model_artifacts/maintenance_duration/maintenance_duration_model.joblib
"""
import sys
import hashlib
from pathlib import Path
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score


def train_and_save_model():
    backend_dir = Path(__file__).resolve().parents[2]
    artifacts_dir = backend_dir / "model_artifacts"
    
    # Locate dataset
    data_path = artifacts_dir / "maintenance_duration" / "maintenance_data.joblib"
    if not data_path.exists():
        data_path = list(artifacts_dir.glob("**/maintenance_data.joblib"))[0]
    
    print(f"Loading dataset from: {data_path}")
    df = joblib.load(data_path)
    
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected DataFrame from {data_path}, got {type(df)}")
    
    print(f"Dataset loaded successfully with shape: {df.shape}")
    
    cat_cols = ["maintenance_type", "department", "asset_type", "complexity", "priority"]
    num_cols = ["workers", "equipment_count", "asset_age_years", "condition_score", "previous_duration_min"]
    target_col = "maintenance_duration_minutes"
    
    X = df[cat_cols + num_cols]
    y = df[target_col]
    
    # Train / Test split (80/20) with fixed seed for full reproducibility
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train records: {len(X_train)}, Test records: {len(X_test)}")
    
    # Preprocessing pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("num", StandardScaler(), num_cols),
        ]
    )
    
    # Full Model Pipeline
    model_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
        ]
    )
    
    print("Training Random Forest Regression Pipeline...")
    model_pipeline.fit(X_train, y_train)
    
    # Evaluation
    y_pred = model_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = root_mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print("=== MODEL EVALUATION RESULTS ===")
    print(f"Mean Absolute Error (MAE)    : {mae:.2f} minutes")
    print(f"Root Mean Squared Error (RMSE): {rmse:.2f} minutes")
    print(f"R-squared (R2 Score)          : {r2:.4f}")
    
    # Save artifact
    output_dir = artifacts_dir / "maintenance_duration"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "maintenance_duration_model.joblib"
    
    joblib.dump(model_pipeline, output_path)
    
    # Compute MD5
    h = hashlib.md5()
    with open(output_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    md5_hash = h.hexdigest()
    
    print(f"Artifact saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")
    print(f"Artifact MD5: {md5_hash}")
    
    return {
        "output_path": str(output_path),
        "md5": md5_hash,
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }


if __name__ == "__main__":
    train_and_save_model()
