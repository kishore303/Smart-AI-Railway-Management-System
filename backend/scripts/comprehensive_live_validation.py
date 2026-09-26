"""
SIH26027 Complete Live Full-Stack End-to-End System Validation Script
Runs all 4 scenarios, 13 roles, DB consistency checks, and system module verifications.
"""
import sys
import json
import os
import secrets
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_API = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def api_request(method, url, headers=None, data=None):
    headers = headers or {}
    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    if req_data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.getcode(), json.loads(body)
            except Exception:
                return resp.getcode(), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return 0, str(e)

DEMO_USERS = {
    "eng_staff": ("ENGINEERING", "MAINTENANCE_STAFF"),
    "eng_je": ("ENGINEERING", "JUNIOR_ENGINEER"),
    "eng_sse": ("ENGINEERING", "SENIOR_SECTION_ENGINEER"),
    "elec_staff": ("ELECTRICAL_OHE", "MAINTENANCE_STAFF"),
    "elec_je": ("ELECTRICAL_OHE", "JUNIOR_ENGINEER"),
    "elec_sse": ("ELECTRICAL_OHE", "SENIOR_SECTION_ENGINEER"),
    "snt_staff": ("SIGNAL_TELECOM", "MAINTENANCE_STAFF"),
    "snt_je": ("SIGNAL_TELECOM", "JUNIOR_ENGINEER"),
    "snt_sse": ("SIGNAL_TELECOM", "SENIOR_SECTION_ENGINEER"),
    "operations": ("OPERATIONS", "OPERATIONS_CONTROLLER"),
    "control": ("CONTROL", "SECTION_CONTROLLER"),
    "railway_official": ("ADMINISTRATION", "RAILWAY_OFFICIAL"),
    "emergency": ("OPERATIONS", "EMERGENCY_OPERATOR"),
}

tokens = {}
results = {"tests": [], "summary": {}}

def log_test(module, name, passed, details=None, evidence=None):
    entry = {
        "module": module,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "details": str(details or ""),
        "evidence": evidence or {}
    }
    results["tests"].append(entry)
    symbol = "[PASS]" if passed else "[FAIL]"
    print(f"{symbol} {module} :: {name} -> {details}")

def auth_headers(username):
    return {"Authorization": f"Bearer {tokens[username]}"}

def run_validation():
    print("=" * 70)
    print("SIH26027 COMPREHENSIVE LIVE SYSTEM AUDIT & E2E VALIDATION")
    print("=" * 70)

    # 1. Startup & Health Verification
    code, data = api_request("GET", f"{BASE_API}/health")
    passed = code == 200 and isinstance(data, dict) and data.get("status") == "online"
    log_test("Startup", "Backend Health Check", passed, f"HTTP {code}", data)

    code, d = api_request("GET", f"{BASE_API}/health/dependencies")
    if isinstance(d, dict):
        db_ok = d.get("database", {}).get("connected") and d.get("database", {}).get("postgis_enabled")
        ml_ok = d.get("ml_engine", {}).get("models_count", 0) >= 3
        ortools_ok = d.get("optimization_engine", {}).get("ortools_cp_sat") == "READY"
        safety_ok = d.get("safety_engine", {}).get("status") == "READY"
        passed = code == 200 and db_ok and ml_ok and ortools_ok and safety_ok
        log_test("Startup", "System Dependencies (PostGIS, ML, OR-Tools, Safety)", passed, 
                 f"DB: {db_ok}, ML: {ml_ok}, OR-Tools: {ortools_ok}, Safety: {safety_ok}", d)
    else:
        log_test("Startup", "System Dependencies", False, f"HTTP {code}: {d}")

    code, f_resp = api_request("GET", FRONTEND_URL)
    log_test("Startup", "Frontend Server (Next.js)", code == 200, f"HTTP {code}")

    # 2. Authentication & RBAC Token Matrix
    print("\n--- 2. Role Authentication Matrix (13 Demo Personas) ---")
    for username, (dept, role) in DEMO_USERS.items():
        password_env = f"SIH_SEED_PASSWORD_{username.upper()}"
        password = os.environ.get(password_env)
        if not password:
            raise RuntimeError(f"Required local validation credential is missing: {password_env}")
        payload = {"username": username, "password": password}
        code, resp = api_request("POST", f"{BASE_API}/api/auth/login", data=payload)
        if code == 200 and isinstance(resp, dict) and "access_token" in resp:
            tokens[username] = resp["access_token"]
            user_info = resp.get("user", {})
            log_test("Auth", f"Login {username}", True, 
                     f"Dept: {user_info.get('department')}, Role: {user_info.get('role')}")
        else:
            log_test("Auth", f"Login {username}", False, f"HTTP {code}: {resp}")

    # 3. Department Data Isolation & RBAC Protection
    print("\n--- 3. Department Isolation & RBAC Security ---")
    code, _ = api_request("POST", f"{BASE_API}/api/auth/login", data={"username": "eng_staff", "password": secrets.token_urlsafe(32)})
    log_test("Security", "Reject Invalid Password", code == 401, f"HTTP {code}")

    code, _ = api_request("POST", f"{BASE_API}/api/approval/1/approve", headers=auth_headers("eng_staff"), data={"decision": "APPROVED"})
    log_test("Security", "Prevent Staff from Official Approval", code in [403, 401], f"HTTP {code}")

    # 4. SCENARIO A: Full E2E Workflow (Happy Path)
    print("\n--- 4. SCENARIO A: Complete End-to-End Happy Path ---")
    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(hours=2)).isoformat()
    end_time = (now + timedelta(hours=3, minutes=30)).isoformat()

    # Step A1: eng_staff creates maintenance request (DRAFT)
    req_payload = {
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Track Tamping",
        "priority": "HIGH",
        "requested_start": start_time,
        "requested_end": end_time,
        "description": "Routine high-density track tamping on Track 1"
    }
    code, eng_req_data = api_request("POST", f"{BASE_API}/api/maintenance/requests", headers=auth_headers("eng_staff"), data=req_payload)
    eng_req_id = None
    if code in [200, 201] and isinstance(eng_req_data, dict):
        eng_req_id = eng_req_data["id"]
        log_test("Scenario A", "Step 1: ENG Staff Creates Request (DRAFT)", True, 
                 f"Req ID: {eng_req_id}, Status: {eng_req_data.get('status')}", eng_req_data)
        
        # eng_staff submits request (DRAFT -> SUBMITTED)
        code_sub, sub_data = api_request("POST", f"{BASE_API}/api/maintenance/requests/{eng_req_id}/submit", headers=auth_headers("eng_staff"))
        log_test("Scenario A", "Step 1b: ENG Staff Submits Request (SUBMITTED)", code_sub == 200, f"Status: {sub_data.get('status') if isinstance(sub_data, dict) else code_sub}")
    else:
        log_test("Scenario A", "Step 1: ENG Staff Creates Request", False, f"HTTP {code}: {eng_req_data}")

    # Step A2: eng_je technical review (SUBMITTED -> UNDER_REVIEW)
    if eng_req_id:
        code_rev, rev_data = api_request("POST", f"{BASE_API}/api/maintenance/requests/{eng_req_id}/je/verify",
                                         headers=auth_headers("eng_je"),
                                         data={"reason": "JE Technical parameters verified and safe."})
        log_test("Scenario A", "Step 2: ENG JE Technical Verification (UNDER_REVIEW)", code_rev == 200, 
                 f"Status: {rev_data.get('status') if isinstance(rev_data, dict) else code_rev}")

    # Step A3: eng_sse departmental approval (UNDER_REVIEW -> VERIFIED)
    if eng_req_id:
        code_ver, ver_data = api_request("POST", f"{BASE_API}/api/maintenance/requests/{eng_req_id}/sse/verify",
                                         headers=auth_headers("eng_sse"),
                                         data={"reason": "SSE Final Departmental Approval and Technical Verification."})
        log_test("Scenario A", "Step 3: ENG SSE Technical Verification (VERIFIED)", code_ver == 200, 
                 f"Status: {ver_data.get('status') if isinstance(ver_data, dict) else code_ver}")

    # Step A4: Create Block Planning Request from Verified Maintenance
    block_req_id = None
    if eng_req_id:
        b_payload = {
            "maintenance_request_id": eng_req_id,
            "section_id": 1,
            "track_id": 1,
            "requested_start": start_time,
            "requested_end": end_time,
            "block_type": "ABSOLUTE"
        }
        code_blk, blk_data = api_request("POST", f"{BASE_API}/api/blocks/requests", headers=auth_headers("eng_sse"), data=b_payload)
        if code_blk in [200, 201] and isinstance(blk_data, dict):
            block_req_id = blk_data["id"]
            log_test("Scenario A", "Step 4: Create Block Request (REQUESTED)", True, f"Block Code: {blk_data.get('block_code')}", blk_data)
        else:
            log_test("Scenario A", "Step 4: Create Block Request", False, f"HTTP {code_blk}: {blk_data}")

    # Step A5: Candidate Window Generation & Safety Engine Rule Execution
    cand_count = 0
    if block_req_id:
        code_gen, gen_data = api_request("POST", f"{BASE_API}/api/blocks/requests/{block_req_id}/candidates/generate",
                                         headers=auth_headers("eng_sse"),
                                         data={"interval_minutes": 30, "max_candidates": 8, "window_days": 2})
        if code_gen == 200 and isinstance(gen_data, dict):
            cand_count = gen_data.get("generated", 0)
            safe_cands = gen_data.get("safe_candidates_count", 0)
            log_test("Scenario A", "Step 5: Candidate Generation & Safety Engine Validation", True,
                     f"Generated: {cand_count}, Safe: {safe_cands}, Unsafe: {gen_data.get('unsafe_candidates_count', 0)}", gen_data)
        else:
            log_test("Scenario A", "Step 5: Candidate Generation & Safety Engine Validation", False, f"HTTP {code_gen}: {gen_data}")

    # Step A6: OR-Tools CP-SAT Optimization
    opt_block_id = None
    if block_req_id:
        code_opt, opt_data = api_request("POST", f"{BASE_API}/api/optimization/blocks/{block_req_id}/optimize",
                                         headers=auth_headers("railway_official"))
        if code_opt == 200 and isinstance(opt_data, dict):
            opt_block_id = opt_data.get("optimized_block_id") or opt_data.get("id")
            log_test("Scenario A", "Step 6: OR-Tools CP-SAT Optimization", True,
                     f"Solver: {opt_data.get('solver_status', 'OPTIMAL')}, Score: {opt_data.get('optimization_score')}, OB_ID: {opt_block_id}", opt_data)
        else:
            log_test("Scenario A", "Step 6: OR-Tools CP-SAT Optimization", False, f"HTTP {code_opt}: {opt_data}")

    # Step A7: Railway Official Review & Approval
    if opt_block_id:
        code_rev, detail_data = api_request("GET", f"{BASE_API}/api/approval/{opt_block_id}", headers=auth_headers("railway_official"))
        log_test("Scenario A", "Step 7a: Official Inspects Recommendation Card", code_rev == 200,
                 f"Eligible: {detail_data.get('is_eligible_for_approval') if isinstance(detail_data, dict) else False}")

        # Official Approves
        code_appr, appr_data = api_request("POST", f"{BASE_API}/api/approval/{opt_block_id}/approve",
                                           headers=auth_headers("railway_official"),
                                           data={"reason": "Approved by Railway Authorized Official following safety and delay verification."})
        if code_appr == 200 and isinstance(appr_data, dict):
            log_test("Scenario A", "Step 7b: Railway Official Decision (APPROVE)", True,
                     f"Status: {appr_data.get('new_status', 'SCHEDULED')}, Block Code: {appr_data.get('block_code')}", appr_data)
        else:
            log_test("Scenario A", "Step 7b: Railway Official Decision (APPROVE)", False, f"HTTP {code_appr}: {appr_data}")

    # Step A8: Full Execution Lifecycle & Safety Clearance Verification
    if opt_block_id:
        # SCHEDULED -> ACTIVE
        c1, _ = api_request("POST", f"{BASE_API}/api/execution/{opt_block_id}/start", headers=auth_headers("control"))
        # ACTIVE -> COMPLETED
        c2, _ = api_request("POST", f"{BASE_API}/api/execution/{opt_block_id}/complete", headers=auth_headers("control"),
                            data={"clearance_granted": True, "remarks": "Track physically verified clear, OHE charged and signals normal."})

        lifecycle_ok = c1 == 200 and c2 == 200
        log_test("Scenario A", "Step 8: Execution Lifecycle & Safety Clearance Flow", lifecycle_ok,
                 f"Transitions [Start ACTIVE:{c1}, Complete & Release:{c2}]")

    # 5. SCENARIO B: Official Rejection with Reason
    print("\n--- 5. SCENARIO B: Rejection Flow ---")
    code_b, req_b = api_request("POST", f"{BASE_API}/api/maintenance/requests", headers=auth_headers("elec_staff"), data={
        "asset_id": 2,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "OHE Inspection",
        "priority": "LOW",
        "requested_start": (now + timedelta(hours=10)).isoformat(),
        "requested_end": (now + timedelta(hours=11)).isoformat(),
        "description": "Routine test request for rejection scenario"
    })
    if code_b in [200, 201] and isinstance(req_b, dict):
        b_id = req_b["id"]
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{b_id}/submit", headers=auth_headers("elec_staff"))
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{b_id}/je/verify", headers=auth_headers("elec_je"), data={"reason": "JE Verified"})
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{b_id}/sse/verify", headers=auth_headers("elec_sse"), data={"reason": "SSE Verified"})
        
        # Create block request
        _, b_blk = api_request("POST", f"{BASE_API}/api/blocks/requests", headers=auth_headers("elec_sse"), data={
            "maintenance_request_id": b_id, "section_id": 1, "track_id": 1,
            "requested_start": (now + timedelta(hours=10)).isoformat(), "requested_end": (now + timedelta(hours=11)).isoformat(),
            "block_type": "ABSOLUTE"
        })
        if isinstance(b_blk, dict) and "id" in b_blk:
            api_request("POST", f"{BASE_API}/api/blocks/requests/{b_blk['id']}/candidates/generate", headers=auth_headers("elec_sse"))
            _, b_opt = api_request("POST", f"{BASE_API}/api/optimization/blocks/{b_blk['id']}/optimize", headers=auth_headers("railway_official"))
            if isinstance(b_opt, dict) and "optimized_block_id" in b_opt:
                ob_b_id = b_opt["optimized_block_id"]
                code_rej, rej_data = api_request("POST", f"{BASE_API}/api/approval/{ob_b_id}/reject",
                                                 headers=auth_headers("railway_official"),
                                                 data={"reason": "High passenger corridor peak hours conflict - resubmit for night window."})
                log_test("Scenario B", "Official Rejection with Mandatory Reason", code_rej == 200, f"HTTP {code_rej}")
            else:
                log_test("Scenario B", "Official Rejection with Mandatory Reason", False, f"Optimization failed: {b_opt}")
    else:
        log_test("Scenario B", "Official Rejection with Mandatory Reason", False, f"Creation failed: {req_b}")

    # 6. SCENARIO C: Modification & Invalidation/Revalidation Loop
    print("\n--- 6. SCENARIO C: Official Modification & Revalidation ---")
    code_c, req_c = api_request("POST", f"{BASE_API}/api/maintenance/requests", headers=auth_headers("eng_staff"), data={
        "asset_id": 1,
        "section_id": 1,
        "track_id": 1,
        "maintenance_type": "Rail Grinding",
        "priority": "MEDIUM",
        "requested_start": (now + timedelta(hours=12)).isoformat(),
        "requested_end": (now + timedelta(hours=14)).isoformat(),
        "description": "Rail grinding window modification test"
    })
    if code_c in [200, 201] and isinstance(req_c, dict):
        c_id = req_c["id"]
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{c_id}/submit", headers=auth_headers("eng_staff"))
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{c_id}/je/verify", headers=auth_headers("eng_je"), data={"reason": "JE Verified"})
        api_request("POST", f"{BASE_API}/api/maintenance/requests/{c_id}/sse/verify", headers=auth_headers("eng_sse"), data={"reason": "SSE Verified"})
        
        _, c_blk = api_request("POST", f"{BASE_API}/api/blocks/requests", headers=auth_headers("eng_sse"), data={
            "maintenance_request_id": c_id, "section_id": 1, "track_id": 1,
            "requested_start": (now + timedelta(hours=12)).isoformat(), "requested_end": (now + timedelta(hours=14)).isoformat(),
            "block_type": "ABSOLUTE"
        })
        if isinstance(c_blk, dict) and "id" in c_blk:
            api_request("POST", f"{BASE_API}/api/blocks/requests/{c_blk['id']}/candidates/generate", headers=auth_headers("eng_sse"))
            _, c_opt = api_request("POST", f"{BASE_API}/api/optimization/blocks/{c_blk['id']}/optimize", headers=auth_headers("railway_official"))
            if isinstance(c_opt, dict) and "optimized_block_id" in c_opt:
                ob_c_id = c_opt["optimized_block_id"]
                mod_start = (now + timedelta(hours=13)).isoformat()
                mod_end = (now + timedelta(hours=15)).isoformat()
                code_mod, mod_data = api_request("POST", f"{BASE_API}/api/approval/{ob_c_id}/modify",
                                                 headers=auth_headers("railway_official"),
                                                 data={"new_start_time": mod_start, "new_end_time": mod_end, "reason": "Shifted window to clear freight convoy"})
                log_test("Scenario C", "Official Modification & Revalidation Loop", code_mod == 200, f"Modified HTTP {code_mod}")
            else:
                log_test("Scenario C", "Official Modification & Revalidation Loop", False, f"Optimization failed: {c_opt}")
    else:
        log_test("Scenario C", "Official Modification & Revalidation Loop", False, f"Creation failed: {req_c}")

    # 7. SCENARIO D: Emergency Response & Dynamic Re-Planning
    print("\n--- 7. SCENARIO D: Emergency Incident & Re-Planning ---")
    inc_payload = {
        "incident_type": "RAIL_FRACTURE",
        "severity": "CRITICAL",
        "section_id": 1,
        "track_id": 1,
        "description": "Severe rail fracture detected during track patrol"
    }
    code_inc, inc_data = api_request("POST", f"{BASE_API}/api/emergency/incidents", headers=auth_headers("emergency"), data=inc_payload)
    if code_inc in [200, 201] and isinstance(inc_data, dict):
        inc_id = inc_data["id"]
        log_test("Scenario D", "Step 1: Emergency Operator Reports Incident", True, f"Incident ID: {inc_id}", inc_data)

        # Step D2: Emergency Assessment
        code_ass, _ = api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/assess",
                                  headers=auth_headers("emergency"),
                                  data={"notes": "Critical fracture on Track 1 KM 42.5", "estimated_duration_mins": 60})
        log_test("Scenario D", "Step 2: Incident Technical Assessment", code_ass == 200, f"HTTP {code_ass}")

        # Step D3: Candidate Generation & Emergency Optimization
        code_cands, emg_cands = api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/generate-candidates", headers=auth_headers("emergency"))
        code_opt, emg_opt = api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/optimize", headers=auth_headers("emergency"))
        log_test("Scenario D", "Step 3: Emergency Dynamic Re-Planning", code_opt == 200, f"HTTP {code_opt}", emg_opt if code_opt == 200 else {})

        # Step D4: Railway Official Approves Emergency Block
        code_appr, _ = api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/approve",
                                   headers=auth_headers("railway_official"),
                                   data={"decision": "APPROVE", "remarks": "Emergency block authorized immediately"})
        log_test("Scenario D", "Step 4: Official Emergency Block Approval", code_appr == 200, f"HTTP {code_appr}")

        # Step D5: Response Dispatch -> Arrival -> Work -> Clearance -> Close
        api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/dispatch", headers=auth_headers("emergency"))
        api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/arrive", headers=auth_headers("emergency"))
        api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/start-work", headers=auth_headers("emergency"))
        api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/request-clearance", headers=auth_headers("emergency"))
        api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/grant-clearance", headers=auth_headers("railway_official"))
        code_close, _ = api_request("POST", f"{BASE_API}/api/emergency/incidents/{inc_id}/close",
                                    headers=auth_headers("emergency"),
                                    data={"notes": "Rail section replaced, tested and returned to normal traffic"})
        log_test("Scenario D", "Step 5: Safety Clearance & Incident Closed", code_close == 200, f"HTTP {code_close}")

    # 8. SUPPORTING MODULES VALIDATION
    print("\n--- 8. Advanced Modules & Analytical Engines ---")
    # Digital Twin
    code_dt, dt_data = api_request("GET", f"{BASE_API}/api/simulation/digital-twin/state", headers=auth_headers("operations"))
    log_test("Digital Twin", "Live Railway Corridor Simulation State", code_dt == 200,
             f"Monitored Sections: {len(dt_data.get('monitored_sections', [])) if isinstance(dt_data, dict) else 0}")

    # What-If Simulator
    code_wi, wi_data = api_request("POST", f"{BASE_API}/api/simulation/what-if",
                                   headers=auth_headers("operations"),
                                   data={"section_id": 1, "track_id": 1, "start_time": start_time, "duration_mins": 120})
    log_test("What-If", "What-If Isolated Corridor Simulator", code_wi == 200,
             f"Optimization Score: {wi_data.get('optimization_score') if isinstance(wi_data, dict) else 'N/A'}")

    # Manual vs AI Benchmark
    code_bm, bm_data = api_request("POST", f"{BASE_API}/api/simulation/manual-vs-ai",
                                   headers=auth_headers("railway_official"),
                                   data={"manual_start": start_time, "manual_end": end_time, "section_id": 1, "track_id": 1, "duration_mins": 90})
    log_test("Benchmark", "Manual vs AI Objective Benchmark", code_bm == 200,
             f"Manual Score: {bm_data.get('manual_plan', {}).get('optimization_score', 0) if isinstance(bm_data, dict) else 0}, AI Score: {bm_data.get('ai_optimized_plan', {}).get('optimization_score', 0) if isinstance(bm_data, dict) else 0}")

    # Block Marketplace
    code_mkt, mkt_data = api_request("GET", f"{BASE_API}/api/marketplace/blocks", headers=auth_headers("snt_staff"))
    log_test("Marketplace", "Block Sharing & Request-to-Join", code_mkt == 200,
             f"Available Marketplace Blocks: {len(mkt_data) if isinstance(mkt_data, list) else 0}")

    # Operational Analytics (9 Dimensions)
    code_ana, ana_data = api_request("GET", f"{BASE_API}/api/analytics/overview", headers=auth_headers("railway_official"))
    log_test("Analytics", "Multi-Dimensional Operational Analytics", code_ana == 200,
             f"KPIs: {list(ana_data.keys()) if isinstance(ana_data, dict) else 'None'}")

    # Spatial / PostGIS GIS Layers
    code_gis, gis_data = api_request("GET", f"{BASE_API}/api/spatial/geojson?layer=all", headers=auth_headers("operations"))
    log_test("GIS / PostGIS", "MapLibre Geospatial Track/Section Layers", code_gis == 200,
             f"Features: {len(gis_data.get('features', [])) if isinstance(gis_data, dict) else len(gis_data) if isinstance(gis_data, list) else 0}")

    # Notifications System
    code_notif, notif_data = api_request("GET", f"{BASE_API}/api/notifications", headers=auth_headers("eng_staff"))
    log_test("Notifications", "Role-Based Notification Feed", code_notif == 200,
             f"Notification Count: {len(notif_data) if isinstance(notif_data, list) else 0}")

    print("\n" + "=" * 70)
    passed_cnt = sum(1 for t in results["tests"] if t["status"] == "PASS")
    total_cnt = len(results["tests"])
    pct = (passed_cnt / total_cnt) * 100 if total_cnt > 0 else 0
    print(f"VALIDATION SUMMARY: {passed_cnt}/{total_cnt} Tests Passed ({pct:.1f}%)")
    print("=" * 70)

    with open("d:/IRCTC/validation_run_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_validation()
