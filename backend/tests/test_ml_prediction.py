"""Module 6 — ML Prediction tests."""
import sys, datetime, hashlib
from pathlib import Path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import engine, SessionLocal
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction

client = TestClient(app)

def login(e,p):
    r=client.post("/api/auth/login", json={"username":e,"password":p})
    assert r.status_code==200, r.text
    return r.json()["access_token"]
def hdr(t): return {"Authorization": f"Bearer {t}"}

tok_eng = login("eng.staff@irctc.test","EngStaff@123")
tok_rev = login("eng.reviewer@irctc.test","EngReview@123")
tok_elec = login("elec.staff@irctc.test","ElecStaff@123")
tok_off = login("railway.official@irctc.test","Official@123")
tok_ops = login("ops.operator@irctc.test","OpsOper@123")

# Clean predictions for determinism
db=SessionLocal()
db.query(MaintenancePrediction).delete()
db.commit()
# Need a maintenance request for persistence tests
from app.database import SessionLocal as SL
db2=SL()
# Find existing ENG request or create one
req = db2.query(MaintenanceRequest).filter(MaintenanceRequest.requested_by==1).first()
if not req:
    # create
    import datetime as dt
    r=client.post("/api/maintenance/requests", headers=hdr(tok_eng), json={"asset_id":1,"section_id":1,"track_id":1,"maintenance_type":"ML Test","priority":"HIGH","requested_start": (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=5)).isoformat(),"requested_end": (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=5,hours=1)).isoformat()})
    req_id=r.json()["id"]
else:
    req_id=req.id
db2.close()
print(f"Using maintenance_request_id={req_id} for persistence tests")

# Helper to get request
def get_req_id():
    return req_id

print("\n=== 1. Genuine Train Impact model loading ===")
from app.ml.loaders import load_train_impact, model_info, clear_cache
clear_cache()
try:
    m=load_train_impact()
    print(f" PASS load_train_impact: {type(m).__name__} steps {[n for n,_ in m.steps]}")
    assert m.steps[1][1].n_estimators==100
    assert m.steps[1][1].random_state==42
    print(" PASS RF100/42 verified")
except Exception as e:
    print(f" FAIL {e}")
    raise
info=model_info("train_impact")
assert info["verified"] and info["md5"]=="6b04723260427bc891736b7ce74adf93"
print(f" PASS MD5 verified {info['md5']}")

print("\n=== 2. Train Impact feature validation & prediction ===")
# Valid
valid_ti={
    "train_number": 12345,
    "train_name": "Rajdhani Express",
    "station_code": "NDLS",
    "station_name": "New Delhi",
    "pct_right_time": 70.0,
    "pct_slight_delay": 15.0,
    "pct_significant_delay": 10.0,
    "pct_cancelled_unknown": 5.0
}
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json=valid_ti)
assert r.status_code==200, r.text
print(f" PASS valid predict delay={r.json()['predicted_delay_mins']} score={r.json()['train_impact_score']}")
assert r.json()["is_demo"]==False
assert "disclaimer" in r.json()
assert "does not approve" in r.json()["disclaimer"]
# Invalid missing
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={"train_number":123})
assert r.status_code==422
print(" PASS missing features 422")
# Invalid type
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={**valid_ti, "train_number":"bad"})
assert r.status_code==422
print(" PASS invalid type 422")
# Invalid range pct >100
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={**valid_ti, "pct_right_time":150})
assert r.status_code==422
print(" PASS invalid range 422")
# Sum not ~100
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={**valid_ti, "pct_right_time":50,"pct_slight_delay":10,"pct_significant_delay":10,"pct_cancelled_unknown":10})
assert r.status_code==422
print(" PASS sum check 422")
# Extra feature
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={**valid_ti, "extra":1})
assert r.status_code==422
print(" PASS extra feature 422")

print("\n=== 3. Persistence for Train Impact (linked to request) ===")
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_eng), json={**valid_ti, "maintenance_request_id": req_id})
assert r.status_code==200
pid=r.json()["persisted_id"]
assert pid is not None
print(f" PASS persisted_id {pid}")
# Verify DB
with engine.connect() as conn:
    row=conn.execute(text("SELECT model_version, input_features, predicted_delay_mins FROM maintenance_predictions WHERE id=:id"), {"id":pid}).fetchone()
    print(f" DB row version={row[0]} features_keys={list(row[1].keys())[:3]} delay={row[2]}")
    assert row[0]=="train_impact_v1_sklearn1.6.1_RF100"
    assert "train_number" in row[1]
    assert row[2] is not None

print("\n=== 4. Genuine Asset Risk model loading ===")
from app.ml.loaders import load_asset_risk
try:
    m=load_asset_risk()
    print(f" PASS load_asset_risk: {type(m).__name__} steps {[n for n,_ in m.steps]} classifier {type(m.steps[1][1]).__name__}")
    assert m.steps[1][1].n_estimators==100
    print(" PASS RF100 verified")
except Exception as e:
    print(f" FAIL {e}")
    raise
info=model_info("asset_risk")
assert info["verified"] and info["md5"]=="3914c6e942b7b3eecfd7ed5481fc5b57"
print(f" PASS MD5 {info['md5']}")

print("\n=== 5. Asset Risk feature validation & prediction (only when explicitly validated) ===")
valid_ar={
    "region":"North","season":"Winter","train_type":"Express","train_age_years":10,"average_speed_kmph":80,"distance_travelled_km":10000,"track_temperature_c":30,"rail_wear_mm":5,"track_vibration_level":2.5,"ballast_condition":"Good","track_curvature_degree":3,"ambient_temperature_c":25,"humidity_percent":60,"rainfall_mm":10,"wind_speed_kmph":15,"wheel_wear_percent":20,"axle_temperature_c":50,"brake_pressure_psi":90,"brake_pad_wear_percent":30,"bearing_temperature_c":60,"battery_voltage":110,"traction_motor_temp_c":70,"signal_system_status":"Normal","power_consumption_kw":500,"load_factor_percent":70,"daily_trips":3,"delay_minutes":10,"last_maintenance_days":45,"inspection_score":75,"sensor_health_index":85,"risk_score":0.5
}
r=client.post("/api/ml/predict/asset-risk", headers=hdr(tok_eng), json=valid_ar)
assert r.status_code==200, r.text
print(f" PASS asset-risk predict risk={r.json()['asset_risk_score']} level={r.json()['risk_level']} is_demo={r.json()['is_demo']}")
assert r.json()["is_demo"]==False
# Missing
r=client.post("/api/ml/predict/asset-risk", headers=hdr(tok_eng), json={"region":"North"})
assert r.status_code==422
print(" PASS missing 422")
# Invalid categorical
r=client.post("/api/ml/predict/asset-risk", headers=hdr(tok_eng), json={**valid_ar, "region":"InvalidRegion"})
assert r.status_code==422
print(" PASS invalid categorical 422")
# Out of range
r=client.post("/api/ml/predict/asset-risk", headers=hdr(tok_eng), json={**valid_ar, "humidity_percent":150})
assert r.status_code==422
print(" PASS out of range 422")
# Persistence linked
r=client.post("/api/ml/predict/asset-risk", headers=hdr(tok_eng), json={**valid_ar, "maintenance_request_id": req_id})
assert r.status_code==200 and r.json()["persisted_id"] is not None
print(f" PASS asset-risk persisted {r.json()['persisted_id']}")

print("\n=== 6. Maintenance Duration dataset NOT model ===")
from app.ml.loaders import load_maintenance_data
import pandas as pd
data=load_maintenance_data()
print(f" PASS load_maintenance_data type {type(data).__name__} shape {data.shape} cols {list(data.columns)[:3]}")
assert isinstance(data, pd.DataFrame)
assert not hasattr(data, "predict")
# Ensure loader guards against predict
info=model_info("maintenance_duration_data")
assert info["verified"]
print(f" PASS MD5 {info['md5']}")
# API should not treat as model
r=client.post("/api/ml/predict/maintenance-duration", headers=hdr(tok_eng), json={"maintenance_type":"Track Tamping","priority":"HIGH","workers":5,"equipment_count":2})
assert r.status_code==200, r.text
print(f" PASS DEMO predict duration={r.json()['predicted_duration_mins']} is_demo={r.json()['is_demo']}")
assert r.json()["is_demo"]==True
assert "DEMO/SYNTHETIC" in r.json()["demo_label"]
assert "NOT FOR PRODUCTION" in r.json()["disclaimer"] or "DEMO" in r.json()["disclaimer"]
print(" PASS DEMO labelling")

print("\n=== 7. Invalid/missing features for duration DEMO ===")
r=client.post("/api/ml/predict/maintenance-duration", headers=hdr(tok_eng), json={"maintenance_type":"x"})
assert r.status_code==422
print(" PASS missing DEMO 422")
r=client.post("/api/ml/predict/maintenance-duration", headers=hdr(tok_eng), json={"maintenance_type":"x","priority":"BAD","workers":5,"equipment_count":2})
assert r.status_code==422
print(" PASS invalid priority DEMO 422")

print("\n=== 8. RBAC ===")
r=client.post("/api/ml/predict/train-impact", json=valid_ti)
assert r.status_code==401
print(" PASS unauth 401")
# Dept scoping: eng creates, elec cannot predict for eng's request
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_elec), json={**valid_ti, "maintenance_request_id": req_id})
assert r.status_code==403, f"cross-dept should be 403 got {r.status_code} {r.text}"
print(" PASS cross-dept 403")
# elec can predict for own request
# Create elec request
r=client.post("/api/maintenance/requests", headers=hdr(tok_elec), json={"asset_id":2,"section_id":1,"track_id":1,"maintenance_type":"ELEC ML","priority":"HIGH","requested_start": ( __import__("datetime").datetime.now(__import__("datetime").timezone.utc)+__import__("datetime").timedelta(days=10)).isoformat(),"requested_end": (__import__("datetime").datetime.now(__import__("datetime").timezone.utc)+__import__("datetime").timedelta(days=10,hours=1)).isoformat()})
rid_e=r.json()["id"]
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_elec), json={**valid_ti, "maintenance_request_id": rid_e})
assert r.status_code==200
print(" PASS same-dept 200")
# Official can predict cross-dept
r=client.post("/api/ml/predict/train-impact", headers=hdr(tok_off), json={**valid_ti, "maintenance_request_id": req_id})
assert r.status_code==200
print(" PASS official cross-dept 200")

print("\n=== 9. Unified endpoint ===")
r=client.post(f"/api/ml/predict/maintenance-request/{req_id}", headers=hdr(tok_eng), json={"train_impact": valid_ti, "maintenance_duration": {"maintenance_type":"Track","priority":"HIGH","workers":5,"equipment_count":2}})
assert r.status_code==200
print(f" PASS unified train+duration {list(r.json()['results'].keys())}")
assert "train_impact" in r.json()["results"] and "maintenance_duration" in r.json()["results"]
assert "disclaimer" in r.json()

print("\n=== 10. Prediction persistence & history ===")
r=client.get(f"/api/ml/predictions/{req_id}", headers=hdr(tok_eng))
assert r.status_code==200
print(f" history len {len(r.json())} for {req_id}")
assert any("train_impact" in p["model_version"] for p in r.json())
# Cross-dept history denied
r=client.get(f"/api/ml/predictions/{req_id}", headers=hdr(tok_elec))
assert r.status_code==403
print(" PASS history dept scope 403")

print("\n=== 11. Audit logging ===")
with engine.connect() as conn:
    rows=conn.execute(text("SELECT action FROM audit_logs WHERE action='RUN_PREDICTION' ORDER BY id DESC LIMIT 10")).fetchall()
    print(f" RUN_PREDICTION audits {len(rows)}")
    assert len(rows)>=5
    print(" PASS audit")

print("\n=== 12. MD5 unchanged ===")
for k, exp in [("train_impact","6b04723260427bc891736b7ce74adf93"),("asset_risk","3914c6e942b7b3eecfd7ed5481fc5b57"),("maintenance_duration_data","bc501e69d592932aad487d0a4909675c")]:
    info=model_info(k)
    assert info["md5"]==exp and info["verified"]
    print(f" PASS {k} MD5 {info['md5']}")

print("\n=== 13. ML never approves ===")
# Try to ensure prediction does not change request status
with engine.connect() as conn:
    s=conn.execute(text("SELECT status FROM maintenance_requests WHERE id=:id"), {"id":req_id}).scalar()
    print(f" request {req_id} status after predictions: {s}")
    assert s in ("DRAFT","SUBMITTED","UNDER_REVIEW","VERIFIED","REVISION_REQUIRED","BLOCK_PLANNING","AI_RECOMMENDATION") # not APPROVED automatically
    print(" PASS status not auto-approved")

print("\n=== 14. Regression 1-5 ===")
import subprocess
for cmd, name in [
    (["python","D:\\IRCTC\\backend\\scripts\\verify_models.py"],"Module1"),
    (["python","D:\\IRCTC\\backend\\tests\\test_auth_rbac.py"],"Module2"),
    (["python","D:\\IRCTC\\backend\\tests\\test_profile.py"],"Module3"),
    (["python","D:\\IRCTC\\backend\\tests\\test_maintenance.py"],"Module4"),
    (["python","D:\\IRCTC\\backend\\tests\\test_review.py"],"Module5"),
]:
    res=subprocess.run(cmd, capture_output=True, text=True)
    ok = "PASSED" in res.stdout or "ALL" in res.stdout
    print(f" {name} {'PASS' if ok else 'FAIL'}: {res.stdout[-200:].strip()[:200]}")
    assert ok, res.stdout[-1000:]

print("\n========== ALL MODULE 6 CHECKS PASSED ==========")

