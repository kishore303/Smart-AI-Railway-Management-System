from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.block import BlockRequest, BlockCandidate, OptimizedBlock, OptimizedBlockSource
from app.models.maintenance import MaintenanceRequest
from app.models.audit import AuditLog
from app.optimizer.config import OptimizationConfig, OptimizationWeights, validate_weights
from app.optimizer.engine import (
    optimize_block_request,
    get_safe_candidates_for_optimization,
    build_candidate_comparison_matrix,
)

router = APIRouter(prefix="/api/optimization", tags=["optimization"])

OPTIMIZATION_ROLES = {"JUNIOR_ENGINEER", "SENIOR_SECTION_ENGINEER", "CONTROLLER", "AUTHORIZED_OFFICIAL"}


class OptimizationWeightsPayload(BaseModel):
    train_delay_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    affected_trains_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    block_duration_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    maintenance_priority_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    cross_dept_coordination_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    resource_utilization_weight: Optional[float] = Field(None, ge=0.0, le=1.0)


class OptimizeRequestPayload(BaseModel):
    weights: Optional[OptimizationWeightsPayload] = None
    time_limit_seconds: Optional[float] = Field(None, ge=1.0, le=60.0)
    num_workers: Optional[int] = Field(None, ge=1, le=16)
    random_seed: Optional[int] = None
    simulation: Optional[bool] = False


class SimulationPayload(BaseModel):
    block_request_id: Optional[int] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    weights: Optional[OptimizationWeightsPayload] = None
    time_limit_seconds: Optional[float] = Field(None, ge=1.0, le=60.0)


@router.get("/config")
def get_optimization_config(current_user: User = Depends(get_current_active_user)):
    cfg = OptimizationConfig()
    return {
        "version": cfg.version,
        "scale_factor": cfg.scale_factor,
        "solver_time_limit_seconds": cfg.solver_time_limit_seconds,
        "solver_workers": cfg.solver_workers,
        "solver_random_seed": cfg.solver_random_seed,
        "default_weights": {
            "train_delay_weight": cfg.weights.train_delay_weight,
            "affected_trains_weight": cfg.weights.affected_trains_weight,
            "block_duration_weight": cfg.weights.block_duration_weight,
            "maintenance_priority_weight": cfg.weights.maintenance_priority_weight,
            "cross_dept_coordination_weight": cfg.weights.cross_dept_coordination_weight,
            "resource_utilization_weight": cfg.weights.resource_utilization_weight,
        },
    }


@router.post("/blocks/{request_id}/optimize")
def run_optimization(
    request_id: int,
    payload: Optional[OptimizeRequestPayload] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in OPTIMIZATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {current_user.role} cannot trigger block optimization."
        )

    blk = db.query(BlockRequest).filter(
        (BlockRequest.id == request_id) | (BlockRequest.maintenance_request_id == request_id)
    ).first()
    if not blk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()
    if mreq and not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    cfg = OptimizationConfig()
    if payload and payload.weights:
        w_dict = payload.weights.model_dump(exclude_unset=True)
        if w_dict:
            tot = sum(w_dict.values())
            if tot > 0:
                custom_w = OptimizationWeights(
                    train_delay_weight=w_dict.get("train_delay_weight", 0.0) / tot,
                    affected_trains_weight=w_dict.get("affected_trains_weight", 0.0) / tot,
                    block_duration_weight=w_dict.get("block_duration_weight", 0.0) / tot,
                    maintenance_priority_weight=w_dict.get("maintenance_priority_weight", 0.0) / tot,
                    cross_dept_coordination_weight=w_dict.get("cross_dept_coordination_weight", 0.0) / tot,
                    resource_utilization_weight=w_dict.get("resource_utilization_weight", 0.0) / tot,
                )
                validate_weights(custom_w)
                cfg.weights = custom_w

    if payload:
        if payload.time_limit_seconds:
            cfg.solver_time_limit_seconds = payload.time_limit_seconds
        if payload.num_workers:
            cfg.solver_workers = payload.num_workers
        if payload.random_seed is not None:
            cfg.solver_random_seed = payload.random_seed

    is_sim = payload.simulation if payload else False

    result = optimize_block_request(
        block_request_id=blk.id,
        db=db,
        config=cfg,
        user_id=current_user.id,
        simulation=is_sim,
    )
    return result


@router.post("/blocks/{request_id}/reoptimize")
def reoptimize_block(
    request_id: int,
    payload: Optional[OptimizeRequestPayload] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return run_optimization(request_id=request_id, payload=payload, current_user=current_user, db=db)


@router.post("/simulate")
def simulate_optimization(
    payload: SimulationPayload,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not payload.block_request_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="block_request_id is required for simulation")

    req_payload = OptimizeRequestPayload(
        weights=payload.weights,
        time_limit_seconds=payload.time_limit_seconds,
        simulation=True,
    )
    return run_optimization(
        request_id=payload.block_request_id,
        payload=req_payload,
        current_user=current_user,
        db=db,
    )


@router.get("/blocks/{request_id}")
def get_latest_optimization(
    request_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    blk = db.query(BlockRequest).filter(
        (BlockRequest.id == request_id) | (BlockRequest.maintenance_request_id == request_id)
    ).first()
    if not blk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()
    if mreq and not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == blk.id).order_by(OptimizedBlockSource.id.desc()).first()
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No optimization result found for this block request")

    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == src.optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")

    selected_candidate = db.query(BlockCandidate).filter(
        BlockCandidate.selected_optimized_block_id == ob.id
    ).first()

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
        "start_time": ob.start_time.isoformat() if ob.start_time else None,
        "end_time": ob.end_time.isoformat() if ob.end_time else None,
        "total_duration_mins": ob.total_duration_mins,
        "total_delay_mins": ob.total_delay_mins,
        "affected_train_count": ob.affected_train_count,
        "combined_departments": ob.combined_departments,
        "explanation": ob.recommendation_reason,
        "selected_candidate_id": selected_candidate.id if selected_candidate else None,
        "created_at": ob.created_at.isoformat() if ob.created_at else None,
    }


@router.get("/blocks/{request_id}/comparison")
def get_candidate_comparison(
    request_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    blk = db.query(BlockRequest).filter(
        (BlockRequest.id == request_id) | (BlockRequest.maintenance_request_id == request_id)
    ).first()
    if not blk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")

    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == blk.maintenance_request_id).first()
    if mreq and not can_access_department_resource(current_user, mreq.department_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")

    matrix = build_candidate_comparison_matrix(blk.id, db)
    return {"block_request_id": blk.id, "candidates": matrix}


@router.get("/blocks/{request_id}/history")
def get_optimization_history(
    request_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    blk = db.query(BlockRequest).filter(
        (BlockRequest.id == request_id) | (BlockRequest.maintenance_request_id == request_id)
    ).first()
    if not blk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block request not found")

    sources = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.block_request_id == blk.id).all()
    ob_ids = [s.optimized_block_id for s in sources]

    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "OptimizedBlock",
        AuditLog.entity_id.in_(ob_ids),
    ).order_by(AuditLog.created_at.desc()).all()

    return {
        "block_request_id": blk.id,
        "history": [
            {
                "id": l.id,
                "action": l.action,
                "optimized_block_id": l.entity_id,
                "user_id": l.user_id,
                "old_status": l.old_status,
                "new_status": l.new_status,
                "description": l.description,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    }
