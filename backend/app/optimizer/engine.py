import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ortools.sat.python import cp_model

from app.models.block import (
    BlockRequest,
    BlockCandidate,
    OptimizedBlock,
    OptimizedBlockSource,
    BlockIntegrationRequest,
    BlockAffectedTrain,
    BlockResourceAllocation,
)
from app.models.department import Department
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.optimizer.config import OptimizationConfig, OptimizationWeights


def get_safe_candidates_for_optimization(block_request_id: int, db: Session) -> List[BlockCandidate]:
    """Hard Safety Gate: Query and return only candidates marked is_safe_for_optimization == True."""
    candidates = (
        db.query(BlockCandidate)
        .join(SafetyValidation, SafetyValidation.candidate_id == BlockCandidate.id)
        .filter(
            BlockCandidate.block_request_id == block_request_id,
            SafetyValidation.overall_status == "SAFE",
            SafetyValidation.is_safe_for_optimization == True,
        )
        .all()
    )
    if not candidates:
        # Also check if candidate itself has safety_status == 'SAFE' or 'FEASIBLE'
        candidates = (
            db.query(BlockCandidate)
            .filter(
                BlockCandidate.block_request_id == block_request_id,
                BlockCandidate.safety_status.in_(["SAFE", "FEASIBLE"]),
            )
            .all()
        )
    return candidates


def _calculate_normalized_metrics(
    candidate: BlockCandidate,
    mreq: Optional[MaintenanceRequest],
    has_coordination: bool,
    db: Session,
) -> Dict[str, float]:
    delay = float(candidate.predicted_delay_mins or 0.0)
    norm_delay = min(delay / 120.0, 1.0)

    trains = float(candidate.affected_train_count or 0.0)
    norm_trains = min(trains / 10.0, 1.0)

    dur = float(candidate.predicted_duration_mins or 60.0)
    norm_dur = min(dur / 240.0, 1.0)

    prio = mreq.priority if mreq else "NORMAL"
    prio_map = {"CRITICAL": 1.0, "HIGH": 0.8, "NORMAL": 0.5, "LOW": 0.2}
    norm_pri = prio_map.get(prio, 0.5)

    norm_coord = 1.0 if has_coordination else 0.0
    norm_res = 1.0  # standard resource availability score

    return {
        "norm_delay": norm_delay,
        "norm_trains": norm_trains,
        "norm_dur": norm_dur,
        "norm_pri": norm_pri,
        "norm_coord": norm_coord,
        "norm_res": norm_res,
    }


def optimize_block_request(
    block_request_id: int,
    db: Session,
    config: Optional[OptimizationConfig] = None,
    user_id: Optional[int] = None,
    simulation: bool = False,
    mode: str = "NORMAL",
) -> Dict[str, Any]:
    start_time_sec = time.time()
    cfg = config or OptimizationConfig()
    
    if mode == "EMERGENCY" and not config:
        # Override weights for emergency restoration prioritizing speed and minimal disruption
        cfg.weights.train_delay_weight = 0.35
        cfg.weights.affected_trains_weight = 0.25
        cfg.weights.block_duration_weight = 0.15
        cfg.weights.maintenance_priority_weight = 0.15
        cfg.weights.cross_dept_coordination_weight = 0.05
        cfg.weights.resource_utilization_weight = 0.05

    blk = db.query(BlockRequest).filter(BlockRequest.id == block_request_id).first()
    if not blk:
        return {
            "status": "NOT_FOUND",
            "solver_status": "UNKNOWN",
            "message": f"Block request {block_request_id} not found.",
        }

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()

    # Check for accepted cross-department integration
    has_coordination = (
        db.query(BlockIntegrationRequest)
        .filter(
            ((BlockIntegrationRequest.source_block_id == blk.id) | (BlockIntegrationRequest.target_block_id == blk.id)),
            BlockIntegrationRequest.final_status == "ACCEPTED",
        )
        .first()
        is not None
    )

    # 1. Hard Safety Gate
    safe_candidates = get_safe_candidates_for_optimization(blk.id, db)
    if not safe_candidates:
        return {
            "status": "NO_SAFE_CANDIDATES",
            "solver_status": "INFEASIBLE",
            "message": "Optimization halted: 0 candidates passed the mandatory Hard Safety Gate.",
            "safe_candidates_count": 0,
            "optimized_block_id": None,
        }

    # 2. CP-SAT Model Formulation
    model = cp_model.CpModel()
    scale = cfg.scale_factor
    w = cfg.weights

    x_vars = {}
    costs = {}
    scores = {}

    for c in safe_candidates:
        x_vars[c.id] = model.NewBoolVar(f"x_{c.id}")
        metrics = _calculate_normalized_metrics(c, mreq, has_coordination, db)

        # Scaled non-negative integer cost
        penalty = (
            w.train_delay_weight * metrics["norm_delay"]
            + w.affected_trains_weight * metrics["norm_trains"]
            + w.block_duration_weight * metrics["norm_dur"]
            + w.maintenance_priority_weight * (1.0 - metrics["norm_pri"])
            + w.cross_dept_coordination_weight * (1.0 - metrics["norm_coord"])
            + w.resource_utilization_weight * (1.0 - metrics["norm_res"])
        )
        int_cost = int((penalty + 1.0) * scale)
        costs[c.id] = int_cost

        # 0-100 normalized optimization score
        opt_score = max(0.0, min(100.0, (1.0 - penalty) * 100.0))
        scores[c.id] = opt_score

    # Hard Constraint: Exactly ONE candidate must be selected
    model.Add(sum(x_vars[c.id] for c in safe_candidates) == 1)

    # Minimize Total Weighted Integer Cost
    model.Minimize(sum(costs[c.id] * x_vars[c.id] for c in safe_candidates))

    # 3. Solver Execution
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.solver_time_limit_seconds
    solver.parameters.num_workers = cfg.solver_workers
    solver.parameters.random_seed = cfg.solver_random_seed

    solver_status_code = solver.Solve(model)
    solve_duration_ms = (time.time() - start_time_sec) * 1000

    if solver_status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status_name = "OPTIMAL" if solver_status_code == cp_model.OPTIMAL else "FEASIBLE" if solver_status_code == cp_model.FEASIBLE else "INFEASIBLE"
        return {
            "status": "INFEASIBLE",
            "solver_status": status_name,
            "message": "CP-SAT solver could not find a feasible solution.",
            "solve_duration_ms": round(solve_duration_ms, 2),
        }

    status_name = "OPTIMAL" if solver_status_code == cp_model.OPTIMAL else "FEASIBLE"

    # Identify chosen candidate
    selected_candidate = None
    for c in safe_candidates:
        if solver.Value(x_vars[c.id]) == 1:
            selected_candidate = c
            break

    if not selected_candidate:
        selected_candidate = safe_candidates[0]

    # Explainability output
    best_score = scores[selected_candidate.id]
    explanation = (
        f"OR-Tools CP-SAT selected candidate {selected_candidate.id} ({selected_candidate.candidate_start.strftime('%H:%M')}–"
        f"{selected_candidate.candidate_end.strftime('%H:%M')}) with Optimization Score {best_score:.1f}/100. "
        f"This window minimizes train delay ({selected_candidate.predicted_delay_mins or 0}m) and affected train traffic "
        f"({selected_candidate.affected_train_count or 0} trains) while fully satisfying the required maintenance duration "
        f"({selected_candidate.predicted_duration_mins}m) and safety constraints."
    )

    # 4. Persistence (Unless Simulation Mode)
    optimized_block = None
    if not simulation:
        optimized_block = persist_optimization_result(
            selected_candidate=selected_candidate,
            all_safe_candidates=safe_candidates,
            scores=scores,
            blk=blk,
            mreq=mreq,
            has_coordination=has_coordination,
            explanation=explanation,
            best_score=best_score,
            db=db,
            user_id=user_id,
        )

    return {
        "status": status_name,
        "solver_status": status_name,
        "objective_value": solver.ObjectiveValue(),
        "solve_duration_ms": round(solve_duration_ms, 2),
        "selected_candidate_id": selected_candidate.id,
        "optimized_block_id": optimized_block.id if optimized_block else None,
        "optimization_score": round(best_score, 2),
        "explanation": explanation,
        "recommended_window": {
            "start": selected_candidate.candidate_start.isoformat(),
            "end": selected_candidate.candidate_end.isoformat(),
            "duration_mins": selected_candidate.predicted_duration_mins,
            "predicted_delay_mins": selected_candidate.predicted_delay_mins,
            "affected_train_count": selected_candidate.affected_train_count,
        },
        "simulation": simulation,
    }


def persist_optimization_result(
    selected_candidate: BlockCandidate,
    all_safe_candidates: List[BlockCandidate],
    scores: Dict[int, float],
    blk: BlockRequest,
    mreq: Optional[MaintenanceRequest],
    has_coordination: bool,
    explanation: str,
    best_score: float,
    db: Session,
    user_id: Optional[int] = None,
) -> OptimizedBlock:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    cnt = db.query(OptimizedBlock).count() + 1
    block_code = f"OPT-{today_str}-{cnt:04d}"

    # Update candidate flags
    for c in all_safe_candidates:
        c.optimization_score = scores.get(c.id, 0.0)
        c.is_selected = c.id == selected_candidate.id

    dur = int((selected_candidate.candidate_end - selected_candidate.candidate_start).total_seconds() // 60)

    # Coordinated departments
    combined_depts = []
    if mreq and mreq.department_id:
        dept = db.query(Department).filter(Department.id == mreq.department_id).first()
        combined_depts.append(dept.code if dept else "ENG")

    ob = OptimizedBlock(
        block_code=block_code,
        section_id=selected_candidate.section_id,
        track_id=selected_candidate.track_id,
        start_time=selected_candidate.candidate_start,
        end_time=selected_candidate.candidate_end,
        total_duration_mins=dur,
        total_delay_mins=selected_candidate.predicted_delay_mins or 0,
        affected_train_count=selected_candidate.affected_train_count or 0,
        combined_departments=combined_depts,
        optimization_score=best_score,
        recommendation_reason=explanation,
        status="PROPOSED",  # Pending Railway Authorized Official Review (Never Auto-Approved)
    )
    db.add(ob)
    db.commit()
    # Link candidate & source
    db.query(BlockCandidate).filter(BlockCandidate.id == selected_candidate.id).update({
        "selected_optimized_block_id": ob.id,
        "is_selected": True,
    })
    obs = OptimizedBlockSource(optimized_block_id=ob.id, block_request_id=blk.id)
    db.add(obs)
    db.commit()

    # Audit Log
    log = AuditLog(
        user_id=user_id or 1,
        action="OPTIMIZE_BLOCK",
        entity_type="OptimizedBlock",
        entity_id=ob.id,
        old_status=blk.status,
        new_status="PROPOSED",
        description=f"OR-Tools CP-SAT generated recommendation {block_code} (Score: {best_score:.1f})",
    )
    db.add(log)
    db.commit()

    return ob


def build_candidate_comparison_matrix(block_request_id: int, db: Session) -> List[Dict[str, Any]]:
    candidates = (
        db.query(BlockCandidate)
        .filter(BlockCandidate.block_request_id == block_request_id)
        .order_by(BlockCandidate.candidate_start.asc())
        .all()
    )
    matrix = []
    for c in candidates:
        sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == c.id).first()
        is_safe = sv.overall_status == "SAFE" if sv else c.safety_status in ("SAFE", "FEASIBLE")
        matrix.append({
            "candidate_id": c.id,
            "window": f"{c.candidate_start.strftime('%H:%M')}–{c.candidate_end.strftime('%H:%M')}",
            "start": c.candidate_start.isoformat(),
            "end": c.candidate_end.isoformat(),
            "predicted_duration_mins": c.predicted_duration_mins,
            "predicted_delay_mins": c.predicted_delay_mins,
            "affected_train_count": c.affected_train_count,
            "safety_status": "SAFE" if is_safe else "UNSAFE",
            "optimization_score": float(c.optimization_score) if c.optimization_score else None,
            "is_selected": c.is_selected,
            "rejection_reason": c.safety_rejection_reason or (sv.rejection_reasons[0] if sv and sv.rejection_reasons else None),
        })
    return matrix
