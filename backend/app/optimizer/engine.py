from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
from datetime import datetime, timezone
import math

from ortools.sat.python import cp_model

from app.models.block import BlockCandidate, BlockRequest, OptimizedBlock, OptimizedBlockSource, BlockIntegrationRequest
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.department import Department

# CP-SAT Configuration — deterministic
SOLVER_TIME_LIMIT = 10.0  # seconds
SOLVER_WORKERS = 8
SOLVER_SEED = 42
SCALE = 1000  # for float to int

# Priority weights (penalty, lower is better for higher priority)
PRIORITY_PENALTY = {"CRITICAL": 0, "HIGH": 10, "MEDIUM": 20, "LOW": 30}


def _get_safe_candidates(db: Session, block_request_id: int) -> Tuple[List[BlockCandidate], List[Dict], int]:
    """Safety gate: only SAFE candidates with is_safe_for_optimization true.
    Returns (safe_candidates, excluded_info, total_considered)
    """
    all_cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block_request_id).all()
    total = len(all_cands)
    safe = []
    excluded = []
    for cand in all_cands:
        sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
        if not sv:
            excluded.append({"candidate_id": cand.id, "reason": "missing SafetyValidation"})
            continue
        if sv.overall_status != "SAFE":
            excluded.append({"candidate_id": cand.id, "reason": f"Safety {sv.overall_status}"})
            continue
        if not sv.is_safe_for_optimization:
            excluded.append({"candidate_id": cand.id, "reason": "is_safe_for_optimization false"})
            continue
        # Also ensure planning status is not INFEASIBLE? But safety is authoritative gate, so we allow FEASIBLE only if safety SAFE
        # If planning INFEASIBLE but safety SAFE (should not happen), still allow if safety says SAFE
        safe.append(cand)
    return safe, excluded, total


def _compute_candidate_cost(candidate: BlockCandidate, mreq: MaintenanceRequest, integration_benefit: int = 0) -> int:
    """Weighted objective cost (lower is better). Scaled integers."""
    # Train delay impact (minimize)
    delay = candidate.predicted_delay_mins or 0
    delay_cost = int(delay * 10 * SCALE)  # weight 10

    # Duration (minimize)
    dur = candidate.predicted_duration_mins or int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60)
    duration_cost = int(dur * 2 * SCALE)  # weight 2

    # Asset risk: higher risk should be prioritized (lower penalty for high risk)
    # risk 0-1, penalty = (1 - risk) * 50 * SCALE
    risk = float(candidate.asset_risk_score) if candidate.asset_risk_score is not None else 0.5
    risk_penalty = int((1 - risk) * 50 * SCALE)

    # Priority: lower penalty for higher priority
    priority = mreq.priority if mreq else "MEDIUM"
    prio_penalty = int(PRIORITY_PENALTY.get(priority, 20) * SCALE)

    # Ripple: use delay as proxy, or 0
    ripple_cost = int(delay * 3 * SCALE)  # weight 3

    # Integration benefit: subtract (reward)
    # If candidate's block has accepted integration and this candidate overlaps with target's window, reward
    # For now, integration_benefit passed in (e.g., overlap_duration * 5)
    integration_reward = int(integration_benefit * 5 * SCALE)

    total = delay_cost + duration_cost + risk_penalty + prio_penalty + ripple_cost - integration_reward
    return total


def optimize_block_request(db: Session, block_request_id: int, user_id: int) -> Dict:
    """Run CP-SAT optimization for a single block_request's SAFE candidates.
    Returns explainable result dict.
    """
    block = db.query(BlockRequest).filter(BlockRequest.id == block_request_id).first()
    if not block:
        return {"status": "FAILED", "reason": "Block request not found", "eligible": 0, "excluded": 0}

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
    if not mreq:
        return {"status": "FAILED", "reason": "Maintenance request not found"}

    # Verify maintenance is in eligible planning state (VERIFIED etc.) — not strict for optimization, but check
    # Allow any status except DRAFT/REJECTED? For now, just log
    safe_cands, excluded, total = _get_safe_candidates(db, block_request_id)

    if not safe_cands:
        # No safe candidates
        return {
            "status": "NO_SAFE_CANDIDATES",
            "reason": "No SAFE candidates available — Safety Engine must validate at least one",
            "total_considered": total,
            "eligible": 0,
            "excluded": len(excluded),
            "excluded_details": excluded,
            "selected_candidate_id": None,
            "optimization_score": None,
            "objective_summary": {},
            "explanation": "No safe candidates to optimize — run Safety Engine first",
        }

    # Check for hard constraint: at least one candidate must have valid timing and duration
    # Filter out candidates that fail hard constraints (timing, duration)
    hard_filtered = []
    hard_excluded = []
    for cand in safe_cands:
        # Hard: start < end
        if cand.candidate_start >= cand.candidate_end:
            hard_excluded.append({"candidate_id": cand.id, "reason": "hard: start >= end"})
            continue
        # Hard: duration must fit maintenance required
        dur = int((cand.candidate_end - cand.candidate_start).total_seconds() // 60)
        required = mreq.requested_duration_mins or cand.predicted_duration_mins or dur
        if dur < required:
            hard_excluded.append({"candidate_id": cand.id, "reason": f"hard: duration {dur} < required {required}"})
            continue
        hard_filtered.append(cand)

    if not hard_filtered:
        return {
            "status": "NO_FEASIBLE_SOLUTION",
            "reason": "All SAFE candidates failed hard constraints (timing/duration)",
            "total_considered": total,
            "eligible": len(safe_cands),
            "hard_excluded": hard_excluded,
            "excluded": len(excluded),
            "selected_candidate_id": None,
            "optimization_score": None,
        }

    # For integration benefit: check if this block has accepted integrations
    # If so, for each candidate, compute overlap with target block's requested window and give benefit
    integration_map = {}
    # Find accepted integrations where this block is source or target
    integ_q = db.query(BlockIntegrationRequest).filter(
        ((BlockIntegrationRequest.source_block_id == block_request_id) | (BlockIntegrationRequest.target_block_id == block_request_id)),
        BlockIntegrationRequest.final_status == "ACCEPTED",
    ).all()
    for integ in integ_q:
        # Get the other block
        other_id = integ.target_block_id if integ.source_block_id == block_request_id else integ.source_block_id
        other_block = db.query(BlockRequest).filter(BlockRequest.id == other_id).first()
        if not other_block:
            continue
        # For each candidate, compute overlap with other block's window
        for cand in hard_filtered:
            overlap = max(0, int((min(cand.candidate_end, other_block.requested_end) - max(cand.candidate_start, other_block.requested_start)).total_seconds() // 60))
            if overlap > 0:
                # Benefit proportional to overlap
                integration_map[cand.id] = max(integration_map.get(cand.id, 0), overlap)

    # Build CP-SAT model: select exactly one candidate
    model = cp_model.CpModel()
    # Create BoolVar for each candidate
    var_map = {}
    for cand in hard_filtered:
        var = model.NewBoolVar(f"cand_{cand.id}")
        var_map[cand.id] = var

    # Hard: exactly one selected
    model.Add(sum(var_map.values()) == 1)

    # Hard: conflicting candidates cannot both be selected — for single block, only one, so not needed
    # But if we have multiple candidates that are overlapping with each other, they are alternatives, so exactly one is fine
    # For resource conflicts: if two candidates would use same resource, they are alternatives, not simultaneous, so no extra constraint

    # Build objective: minimize weighted cost
    # Compute cost for each candidate
    costs = {}
    for cand in hard_filtered:
        benefit = integration_map.get(cand.id, 0)
        cost = _compute_candidate_cost(cand, mreq, integration_benefit=benefit)
        costs[cand.id] = cost

    # Objective
    objective_terms = []
    for cid, var in var_map.items():
        objective_terms.append(costs[cid] * var)
    model.Minimize(sum(objective_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = SOLVER_SEED
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "NO_FEASIBLE_SOLUTION",
            "reason": f"CP-SAT solver status {status} — no feasible solution",
            "total_considered": total,
            "eligible": len(safe_cands),
            "hard_excluded": len(hard_excluded),
            "excluded": len(excluded),
            "selected_candidate_id": None,
            "optimization_score": None,
        }

    # Find selected
    selected_id = None
    for cid, var in var_map.items():
        if solver.Value(var) == 1:
            selected_id = cid
            break

    if selected_id is None:
        return {
            "status": "FAILED",
            "reason": "Solver did not select any candidate",
            "total_considered": total,
            "eligible": len(safe_cands),
            "selected_candidate_id": None,
        }

    selected_cand = next(c for c in hard_filtered if c.id == selected_id)
    selected_cost = costs[selected_id]
    # Convert cost to explainable score: lower cost is better, so score = 1000 - (cost / SCALE) normalized?
    # For explainability, compute score as 100 - (cost / (max_cost *1.2)) *100, but simple: score = max(0, 100 - (cost / SCALE)/10)
    # Let's compute max cost among candidates for normalization
    max_cost = max(costs.values()) if costs else 1
    min_cost = min(costs.values()) if costs else 0
    # Score 0-100, higher is better (lower cost = higher score)
    if max_cost == min_cost:
        score = 100.0
    else:
        score = 100.0 * (1 - (selected_cost - min_cost) / (max_cost - min_cost + 1))
        score = round(max(0, min(100, score)), 2)

    # Also compute objective summary
    # Recompute components for selected
    delay = selected_cand.predicted_delay_mins or 0
    dur = selected_cand.predicted_duration_mins or int((selected_cand.candidate_end - selected_cand.candidate_start).total_seconds() // 60)
    risk = float(selected_cand.asset_risk_score) if selected_cand.asset_risk_score is not None else 0.5

    objective_summary = {
        "delay_impact": delay,
        "duration_mins": dur,
        "asset_risk_score": risk,
        "priority": mreq.priority if mreq else None,
        "integration_benefit_mins": integration_map.get(selected_id, 0),
        "total_cost_scaled": selected_cost / SCALE,
        "cost_breakdown": {
            "delay_cost": delay * 10,
            "duration_cost": dur * 2,
            "risk_penalty": (1 - risk) * 50,
            "priority_penalty": PRIORITY_PENALTY.get(mreq.priority if mreq else "MEDIUM", 20),
            "integration_reward": integration_map.get(selected_id, 0) * 5,
        }
    }

    explanation = (
        f"Selected candidate {selected_id} among {len(hard_filtered)} eligible SAFE candidates "
        f"(total {total}, excluded {len(excluded)} unsafe/missing, {len(hard_excluded)} hard-constraint). "
        f"Cost {selected_cost/SCALE:.1f} (delay {delay}*10 + duration {dur}*2 + risk penalty {(1-risk)*50:.1f} + priority {PRIORITY_PENALTY.get(mreq.priority if mreq else 'MEDIUM',20)}"
        f" - integration {integration_map.get(selected_id,0)*5}). "
        f"Score {score}/100. "
        f"Safety gate passed: {selected_id} is SAFE. "
        f"Hard constraints enforced: exactly one, timing valid, duration fits."
    )

    return {
        "status": "OPTIMIZED",
        "total_considered": total,
        "eligible": len(safe_cands),
        "hard_filtered": len(hard_filtered),
        "unsafe_excluded": len(excluded),
        "excluded_details": excluded,
        "hard_excluded": hard_excluded,
        "selected_candidate_id": selected_id,
        "selected_candidate": selected_cand,
        "optimization_score": score,
        "objective_value": selected_cost / SCALE,
        "objective_summary": objective_summary,
        "explanation": explanation,
        "solver_status": status,
        "solver_time": solver.WallTime(),
    }


def create_optimized_block(db: Session, block_request_id: int, optimization_result: dict, user_id: int) -> OptimizedBlock:
    """Create optimized_blocks entry from successful optimization. Only if OPTIMIZED."""
    if optimization_result["status"] != "OPTIMIZED":
        raise ValueError(f"Cannot create optimized block for status {optimization_result['status']}")

    selected_id = optimization_result["selected_candidate_id"]
    candidate = db.query(BlockCandidate).filter(BlockCandidate.id == selected_id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()

    # Generate optimized block code
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    cnt = db.query(OptimizedBlock).count() + 1
    block_code = f"OPT-{today}-{cnt:04d}"

    # Determine combined departments if integrated
    combined = None
    sources = [block.id]
    # Check for accepted integrations for this block
    integ_q = db.query(BlockIntegrationRequest).filter(
        ((BlockIntegrationRequest.source_block_id == block_request_id) | (BlockIntegrationRequest.target_block_id == block_request_id)),
        BlockIntegrationRequest.final_status == "ACCEPTED",
    ).all()
    if integ_q:
        # Collect all departments involved
        dept_ids = {mreq.department_id}
        for integ in integ_q:
            other_id = integ.target_block_id if integ.source_block_id == block_request_id else integ.source_block_id
            other_block = db.query(BlockRequest).filter(BlockRequest.id == other_id).first()
            if other_block:
                other_mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == other_block.maintenance_request_id).first()
                if other_mreq:
                    dept_ids.add(other_mreq.department_id)
                sources.append(other_id)
        # Get codes
        dept_codes = []
        for did in dept_ids:
            dept = db.query(Department).filter(Department.id == did).first()
            if dept:
                dept_codes.append(dept.code)
        combined = dept_codes
    else:
        dept = db.query(Department).filter(Department.id == mreq.department_id).first()
        combined = [dept.code] if dept else None

    ob = OptimizedBlock(
        block_code=block_code,
        section_id=candidate.section_id,
        track_id=candidate.track_id,
        start_time=candidate.candidate_start,
        end_time=candidate.candidate_end,
        total_duration_mins=int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60),
        total_delay_mins=candidate.predicted_delay_mins,
        affected_train_count=candidate.affected_train_count,
        ripple_impact_score=None,  # Could be derived, but leave null for now
        resource_conflict_count=0,
        combined_departments=combined,
        optimization_score=optimization_result["optimization_score"],
        recommendation_reason=optimization_result["explanation"],
        status="PROPOSED",  # Not APPROVED — official must decide
    )
    db.add(ob)
    db.flush()

    # Update candidate
    candidate.is_selected = True
    candidate.optimization_score = optimization_result["optimization_score"]
    candidate.selected_optimized_block_id = ob.id
    db.flush()

    # Create optimized_block_sources
    for src_id in sources:
        obs = OptimizedBlockSource(optimized_block_id=ob.id, block_request_id=src_id)
        db.add(obs)
    db.commit()
    db.refresh(ob)
    return ob
