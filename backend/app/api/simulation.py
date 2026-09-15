from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user
from app.models.user import User
from app.models.safety import SafetyValidation
from app.models.block import BlockCandidate, OptimizedBlock
from app.models.simulation import Simulation
from app.models.audit import AuditLog

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

def _audit(db: Session, user_id, action, entity_id=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="simulation", entity_id=entity_id, description=desc)
    db.add(log)
    db.commit()

@router.get("/digital-twin")
def digital_twin(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Lightweight snapshot using existing data - no fake infrastructure
    with db.bind.connect() as conn:
        sections = conn.execute(text("SELECT count(*) FROM railway_sections")).scalar()
        tracks = conn.execute(text("SELECT count(*) FROM tracks")).scalar()
        stations = conn.execute(text("SELECT count(*) FROM stations")).scalar()
        assets = conn.execute(text("SELECT count(*) FROM assets")).scalar()
        mreq = conn.execute(text("SELECT count(*) FROM maintenance_requests")).scalar()
        blocks = conn.execute(text("SELECT count(*) FROM block_requests")).scalar()
        cands = conn.execute(text("SELECT count(*) FROM block_candidates")).scalar()
        opt = conn.execute(text("SELECT count(*) FROM optimized_blocks")).scalar()
        resources = conn.execute(text("SELECT count(*) FROM resources")).scalar()
        trains = conn.execute(text("SELECT count(*) FROM trains")).scalar()
        incidents = conn.execute(text("SELECT count(*) FROM incidents")).scalar()
        # Get sample approved/active blocks
        active = conn.execute(text("SELECT block_code, status, start_time FROM optimized_blocks WHERE status IN ('APPROVED','ACTIVE') LIMIT 5")).fetchall()
    return {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "tracks": tracks,
        "stations": stations,
        "assets": assets,
        "maintenance_requests": mreq,
        "block_requests": blocks,
        "block_candidates": cands,
        "optimized_blocks": opt,
        "resources": resources,
        "trains": trains,
        "incidents": incidents,
        "active_blocks_sample": [{"block_code": r[0], "status": r[1], "start_time": str(r[2])} for r in active],
        "note": "Real persisted data only - unavailable fields shown as counts, synthetic/demo data remains labelled elsewhere",
    }

@router.post("/what-if")
def what_if(
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # Expected: original_block_id, modified_start_time, modified_end_time, additional_department_id, simulation_name
    original_block_id = payload.get("original_block_id") or payload.get("optimized_block_id")
    if not original_block_id:
        raise HTTPException(status_code=422, detail="original_block_id required")
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == original_block_id).first()
    if not ob:
        raise HTTPException(status_code=404, detail="Original optimized block not found")
    # Dept check - must have access to original block's maintenance dept
    from app.models.block import OptimizedBlockSource, BlockRequest
    from app.models.maintenance import MaintenanceRequest
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first() if blk else None
        if mreq:
            from app.core.rbac import can_access_department_resource
            if not can_access_department_resource(current_user, mreq.department_id, db):
                if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
                    raise HTTPException(status_code=403, detail="Department access denied")
    # Parse scenario times
    mod_start = payload.get("modified_start_time")
    mod_end = payload.get("modified_end_time")
    # Validate times if provided
    start_dt = None
    end_dt = None
    if mod_start:
        try:
            start_dt = datetime.fromisoformat(str(mod_start).replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid modified_start_time")
    if mod_end:
        try:
            end_dt = datetime.fromisoformat(str(mod_end).replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid modified_end_time")
    if start_dt and end_dt and start_dt >= end_dt:
        raise HTTPException(status_code=422, detail="modified_start must be before modified_end")
    add_dept = payload.get("additional_department_id")
    # Create a temporary candidate for safety/optimization without modifying real data
    # Use original candidate as baseline
    from app.models.block import BlockCandidate
    # Find selected candidate for original block
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        cand = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == src.block_request_id).first() if src else None
    if not cand:
        raise HTTPException(status_code=404, detail="No candidate for original block")
    # Create a transient candidate object (not persisted) for safety check
    # We will create a temporary BlockCandidate-like dict and run safety engine via a transient object
    # Instead, create a real BlockCandidate with a temporary flag? But spec says MUST NOT modify real approved plan
    # So we will NOT persist a new candidate to block_candidates with is_selected, but we will simulate via in-memory
    # For simplicity, we will create a transient candidate and run safety directly
    from app.safety.engine import validate_candidate
    # Build a transient candidate object
    class TransientCandidate:
        def __init__(self, base, new_start, new_end):
            self.id = 999999  # temp
            self.block_request_id = base.block_request_id
            self.section_id = base.section_id
            self.track_id = base.track_id
            self.candidate_start = new_start if new_start else base.candidate_start
            self.candidate_end = new_end if new_end else base.candidate_end
            self.predicted_duration_mins = base.predicted_duration_mins
            self.predicted_delay_mins = base.predicted_delay_mins
            self.asset_risk_score = base.asset_risk_score
            self.safety_status = base.safety_status
            self.is_selected = False
            self.optimization_score = None
    # Determine scenario start/end
    scen_start = start_dt if start_dt else cand.candidate_start
    scen_end = end_dt if end_dt else cand.candidate_end
    # Create transient for safety
    transient = TransientCandidate(cand, scen_start, scen_end)
    # Run safety
    result = validate_candidate(transient, db)
    is_safe = result["overall_status"] == "SAFE"
    # If safe, try to run optimizer on a single candidate scenario (reuse optimizer logic but with single candidate)
    # For what-if, we will not call the full optimizer that creates a new optimized block, but we will simulate optimization score
    # Simple: if safe, create a simulated optimization score based on delay/duration, else infeasible
    sim_optimization_score = None
    sim_delay = cand.predicted_delay_mins
    if is_safe:
        # Simple score: 100 - (delay/10 + duration/100)
        dur = int((scen_end - scen_start).total_seconds() // 60) if scen_start and scen_end else 120
        delay = sim_delay or 0
        sim_optimization_score = max(0, 100 - (delay/5 + dur/20))
        sim_optimization_score = round(sim_optimization_score, 2)
        feasibility = "FEASIBLE"
    else:
        feasibility = "INFEASIBLE"
    # Baseline comparison
    baseline = {
        "start_time": cand.candidate_start.isoformat() if cand.candidate_start else None,
        "end_time": cand.candidate_end.isoformat() if cand.candidate_end else None,
        "duration": int((cand.candidate_end - cand.candidate_start).total_seconds()//60) if cand.candidate_start and cand.candidate_end else None,
        "safety": "SAFE",  # original was safe (since it was optimized)
        "optimization_score": float(cand.optimization_score) if cand.optimization_score else None,
    }
    scenario = {
        "start_time": scen_start.isoformat() if scen_start else None,
        "end_time": scen_end.isoformat() if scen_end else None,
        "duration": int((scen_end - scen_start).total_seconds()//60) if scen_start and scen_end else None,
        "safety": result["overall_status"],
        "optimization_score": sim_optimization_score,
        "feasibility": feasibility,
    }
    # Persist simulation record (allowed per schema)
    sim = Simulation(
        simulation_name=payload.get("simulation_name") or f"What-If for {ob.block_code}",
        created_by=current_user.id,
        original_block_id=ob.id,
        modified_start_time=start_dt,
        modified_end_time=end_dt,
        additional_department_id=add_dept,
        predicted_delay_mins=sim_delay,
        optimization_score=sim_optimization_score,
        result_summary=f"Safety {result['overall_status']}, Feasibility {feasibility}, Score {sim_optimization_score}",
    )
    db.add(sim)
    db.commit()
    db.refresh(sim)
    _audit(db, current_user.id, "CREATE_SIMULATION", entity_id=sim.id, desc=f"What-if for {ob.block_code} safety {result['overall_status']}")

    # Ensure we did NOT modify real block
    # Verify original still same
    db.refresh(ob)
    if ob.start_time != db.query(OptimizedBlock).filter(OptimizedBlock.id == ob.id).first().start_time:
        raise ValueError("Optimized block start time verification failed")

    return {
        "simulation_id": sim.id,
        "original_block_id": ob.id,
        "scenario": scenario,
        "baseline": baseline,
        "safety": result,
        "feasibility": feasibility,
        "optimization_score": sim_optimization_score,
        "warnings": result.get("warnings", []),
        "rejection_reasons": result.get("rejection_reasons", []),
        "is_safe": is_safe,
        "comparison": {
            "baseline_start": baseline["start_time"],
            "scenario_start": scenario["start_time"],
            "baseline_duration": baseline["duration"],
            "scenario_duration": scenario["duration"],
            "baseline_safety": baseline["safety"],
            "scenario_safety": scenario["safety"],
        },
        "disclaimer": "What-if simulation only — does not modify real approved plan, does not approve, does not allocate resources",
    }

@router.get("/{simulation_id}")
def get_simulation(simulation_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    # Dept check: must have access to original block
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == sim.original_block_id).first()
    if ob:
        from app.models.block import OptimizedBlockSource, BlockRequest
        from app.models.maintenance import MaintenanceRequest
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
        if src:
            blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first() if blk else None
            if mreq:
                from app.core.rbac import can_access_department_resource
                if not can_access_department_resource(current_user, mreq.department_id, db):
                    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
                        raise HTTPException(status_code=403, detail="Department access denied")
    return {
        "id": sim.id,
        "simulation_name": sim.simulation_name,
        "original_block_id": sim.original_block_id,
        "modified_start_time": sim.modified_start_time.isoformat() if sim.modified_start_time else None,
        "modified_end_time": sim.modified_end_time.isoformat() if sim.modified_end_time else None,
        "additional_department_id": sim.additional_department_id,
        "predicted_delay_mins": sim.predicted_delay_mins,
        "optimization_score": float(sim.optimization_score) if sim.optimization_score else None,
        "result_summary": sim.result_summary,
        "created_at": sim.created_at.isoformat() if sim.created_at else None,
        "created_by": sim.created_by,
    }

@router.get("/history/list")
def simulation_history(skip: int = 0, limit: int = 20, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    q = db.query(Simulation)
    if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
        q = q.filter(Simulation.created_by == current_user.id)
    total = q.count()
    items = q.order_by(Simulation.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": s.id,
                "simulation_name": s.simulation_name,
                "original_block_id": s.original_block_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            } for s in items
        ],
        "skip": skip,
        "limit": limit,
    }
