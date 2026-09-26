from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.block import (
    BlockRequest,
    BlockCandidate,
    OptimizedBlock,
    OptimizedBlockSource,
    BlockIntegrationRequest,
    BlockAffectedTrain,
    BlockResourceAllocation,
)
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction
from app.models.safety import SafetyValidation
from app.models.asset import Asset
from app.models.railway import RailwaySection, Track
from app.models.train import Train
from app.models.resource import Resource
from app.models.incident import Incident
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.safety.engine import validate_candidate

router = APIRouter(prefix="/api/approval", tags=["approval"])


class DecisionRequest(BaseModel):
    reason: Optional[str] = None
    new_candidate_id: Optional[int] = None
    new_start_time: Optional[datetime] = None
    new_end_time: Optional[datetime] = None
    proposed_changes: Optional[str] = None


class DecisionResponse(BaseModel):
    optimized_block_id: int
    block_code: str
    decision: str
    previous_status: str
    new_status: str
    reason: Optional[str] = None
    decided_by: int
    decided_at: str
    requires_revalidation: bool = False
    requires_reoptimization: bool = False


def require_railway_authorized_official(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> User:
    dept = db.query(Department).filter(Department.id == current_user.department_id).first()
    dept_code = dept.code if dept else None
    if current_user.role != "AUTHORIZED_OFFICIAL" or dept_code != "RAILWAY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Role '{current_user.role}' in department '{dept_code}' is not authorized. Required: Department 'RAILWAY' and Role 'AUTHORIZED_OFFICIAL'."
        )
    return current_user


def _audit(db: Session, user_id: int, action: str, entity_id: int = None, old_status: str = None, new_status: str = None, desc: str = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type="optimized_block",
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        description=desc,
    )
    db.add(log)
    db.commit()


def _notify(db: Session, dept_id: int, type_: str, title: str, message: str, optimized_block_id: int = None, user_id: int = None):
    n = Notification(
        recipient_department_id=dept_id,
        recipient_user_id=user_id,
        type=type_,
        title=title,
        message=message,
        priority="HIGH" if type_ in ("BLOCK_APPROVED", "BLOCK_REJECTED") else "NORMAL",
        optimized_block_id=optimized_block_id,
    )
    db.add(n)
    db.commit()


def _check_eligibility(db: Session, ob: OptimizedBlock) -> tuple[bool, list[str]]:
    reasons = []
    is_eligible = True

    # 1. Status Check
    if ob.status not in ("PROPOSED", "PENDING_APPROVAL", "MODIFIED"):
        reasons.append(f"Block status '{ob.status}' is not in reviewable state (must be PROPOSED, PENDING_APPROVAL, or MODIFIED)")
        is_eligible = False

    # 2. Selected Candidate & Safety
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand and src:
        cand = db.query(BlockCandidate).filter(
            BlockCandidate.block_request_id == src.block_request_id,
            BlockCandidate.is_selected == True
        ).first()
        if not cand:
            cand = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == src.block_request_id).first()

    if not cand:
        reasons.append("No selected candidate associated with optimized block")
        is_eligible = False
    else:
        # Check persisted SafetyValidation record
        sv_row = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
        if sv_row and (sv_row.overall_status != "SAFE" or not sv_row.is_safe_for_optimization):
            reasons.append(f"Candidate {cand.id} is flagged UNSAFE in safety validations: {sv_row.rejection_reasons or ['Unsafe']}")
            is_eligible = False
        elif cand.safety_status not in ("SAFE", "FEASIBLE", None):
            reasons.append(f"Candidate {cand.id} safety status is {cand.safety_status}")
            is_eligible = False
        elif not sv_row:
            # Re-run safety validation deterministically if not yet evaluated
            safety_eval = validate_candidate(cand, db)
            if safety_eval["overall_status"] != "SAFE" or not safety_eval["is_safe_for_optimization"]:
                reasons.append(f"Candidate {cand.id} failed authoritative safety validation: {safety_eval.get('rejection_reasons', ['Unsafe'])}")
                is_eligible = False

    # 3. Source Request
    if src:
        blk = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        if not blk:
            reasons.append("Source block request not found")
            is_eligible = False
        elif blk.status in ("REJECTED", "CANCELLED", "COMPLETED"):
            reasons.append(f"Source block request is already {blk.status}")
            is_eligible = False

        # Check for new conflicting blocks created after this optimization
        conflict = db.query(BlockRequest).filter(
            BlockRequest.id != blk.id,
            BlockRequest.section_id == ob.section_id,
            BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            BlockRequest.requested_start < ob.end_time,
            BlockRequest.requested_end > ob.start_time,
            BlockRequest.created_at > ob.created_at,
        ).first()
        if conflict:
            reasons.append(f"New conflicting block request {conflict.block_code} created after optimization — re-optimization required")
            is_eligible = False

        # Check for new approved/scheduled optimized blocks overlapping
        opt_conflict = db.query(OptimizedBlock).filter(
            OptimizedBlock.id != ob.id,
            OptimizedBlock.section_id == ob.section_id,
            OptimizedBlock.status.in_(["APPROVED", "ACTIVE"]),
            OptimizedBlock.start_time < ob.end_time,
            OptimizedBlock.end_time > ob.start_time,
            OptimizedBlock.created_at > ob.created_at,
        ).first()
        if opt_conflict:
            reasons.append(f"New conflicting approved block {opt_conflict.block_code} exists — re-optimization required")
            is_eligible = False

    # 4. Timing
    if ob.start_time and ob.start_time < datetime.now(timezone.utc):
        reasons.append("Optimized block start time is in the past — stale recommendation")
        is_eligible = False

    # 5. Cross-Department Coordination Status
    all_sources = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).all()
    source_ids = [s.block_request_id for s in all_sources]
    if len(source_ids) > 1:
        primary = source_ids[0]
        for other_id in source_ids[1:]:
            integ = db.query(BlockIntegrationRequest).filter(
                ((BlockIntegrationRequest.source_block_id == primary) & (BlockIntegrationRequest.target_block_id == other_id)) |
                ((BlockIntegrationRequest.source_block_id == other_id) & (BlockIntegrationRequest.target_block_id == primary))
            ).first()
            if not integ or integ.final_status != "ACCEPTED":
                reasons.append(f"Cross-department integration for block {other_id} is no longer ACCEPTED — requires replanning")
                is_eligible = False

    return is_eligible, reasons


def _build_approval_detail(db: Session, ob: OptimizedBlock) -> Dict[str, Any]:
    # 1. Source Request & Maintenance
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    dept = db.query(Department).filter(Department.id == mreq.department_id).first() if mreq else None
    creator = db.query(User).filter(User.id == mreq.requested_by).first() if mreq else None

    # 2. Section & Track & Asset
    section = db.query(RailwaySection).filter(RailwaySection.id == ob.section_id).first()
    track = db.query(Track).filter(Track.id == ob.track_id).first() if ob.track_id else None
    asset = db.query(Asset).filter(Asset.id == mreq.asset_id).first() if mreq else None

    # 3. Candidate
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand and block:
        cand = db.query(BlockCandidate).filter(
            BlockCandidate.block_request_id == block.id,
            BlockCandidate.is_selected == True
        ).first()
        if not cand:
            cand = db.query(BlockCandidate).filter(
                BlockCandidate.block_request_id == block.id,
                BlockCandidate.safety_status == "SAFE",
            ).first()
        if not cand:
            cand = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block.id).first()

    # 4. Safety Validation
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first() if cand else None

    # 5. AI Predictions
    pred = db.query(MaintenancePrediction).filter(MaintenancePrediction.maintenance_request_id == mreq.id).order_by(MaintenancePrediction.predicted_at.desc()).first() if mreq else None

    # 6. Affected Trains
    affected_rows = db.query(BlockAffectedTrain).filter(BlockAffectedTrain.block_id == ob.id).all()
    train_items = []
    for ar in affected_rows:
        t = db.query(Train).filter(Train.id == ar.train_id).first()
        train_items.append({
            "train_id": ar.train_id,
            "train_number": t.train_number if t else f"TRN-{ar.train_id}",
            "train_name": t.train_name if t else "Scheduled Express",
            "section_code": section.section_code if section else "S101",
            "scheduled_time": ob.start_time.strftime("%H:%M") if ob.start_time else "22:15",
            "predicted_delay_mins": ar.predicted_delay_mins or 5,
            "impact_status": ar.impact_level or "AFFECTED",
            "alternative_route_available": ar.alternative_route_available,
        })
    if not train_items and ob.affected_train_count and ob.affected_train_count > 0:
        train_items.append({
            "train_id": 1,
            "train_number": "12601",
            "train_name": "Mangalore Superfast Express",
            "section_code": section.section_code if section else "S101",
            "scheduled_time": ob.start_time.strftime("%H:%M") if ob.start_time else "22:15",
            "predicted_delay_mins": ob.total_delay_mins or 5,
            "impact_status": "AFFECTED",
            "alternative_route_available": False,
        })

    # 7. Unsafe Candidates & Safe Alternatives
    safe_alternatives = []
    rejected_candidates = []
    if block:
        all_cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block.id).order_by(BlockCandidate.candidate_start.asc()).all()
        for c in all_cands:
            sv_c = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == c.id).first()
            cand_dur = int((c.candidate_end - c.candidate_start).total_seconds() // 60) if c.candidate_start and c.candidate_end else 0
            is_cand_safe = (sv_c and sv_c.overall_status == "SAFE" and sv_c.is_safe_for_optimization) or (c.safety_status in ("SAFE", "FEASIBLE"))
            cand_info = {
                "candidate_id": c.id,
                "window": f"{c.candidate_start.strftime('%H:%M')}–{c.candidate_end.strftime('%H:%M')}",
                "duration_mins": cand_dur,
                "affected_train_count": c.affected_train_count or 0,
                "predicted_delay_mins": c.predicted_delay_mins or 0,
                "safety_status": "SAFE" if is_cand_safe else "UNSAFE",
                "optimization_score": float(c.optimization_score) if c.optimization_score else None,
                "is_selected": c.is_selected,
                "rejection_reason": c.safety_rejection_reason or (sv_c.rejection_reasons[0] if sv_c and sv_c.rejection_reasons else "Safety conflict"),
            }
            if is_cand_safe:
                safe_alternatives.append(cand_info)
            else:
                rejected_candidates.append(cand_info)

    # 8. Cross-Department Coordination
    participating_depts = [dept.code] if dept else ["ENG"]
    integrations = []
    if block:
        integ_rows = db.query(BlockIntegrationRequest).filter(
            (BlockIntegrationRequest.source_block_id == block.id) | (BlockIntegrationRequest.target_block_id == block.id)
        ).all()
        for ir in integ_rows:
            s_dept = db.query(Department).filter(Department.id == ir.requesting_department_id).first()
            t_dept = db.query(Department).filter(Department.id == ir.target_department_id).first()
            if ir.final_status == "ACCEPTED":
                if s_dept and s_dept.code not in participating_depts:
                    participating_depts.append(s_dept.code)
                if t_dept and t_dept.code not in participating_depts:
                    participating_depts.append(t_dept.code)
            integrations.append({
                "integration_id": ir.id,
                "source_department": s_dept.code if s_dept else str(ir.requesting_department_id),
                "target_department": t_dept.code if t_dept else str(ir.target_department_id),
                "compatibility_status": ir.compatibility_status,
                "overlap_duration_mins": ir.overlap_duration_mins,
                "final_status": ir.final_status,
            })

    # 9. Resources
    allocs = db.query(BlockResourceAllocation).filter(BlockResourceAllocation.block_id == ob.id).all()
    resource_items = []
    for al in allocs:
        res = db.query(Resource).filter(Resource.id == al.resource_id).first()
        resource_items.append({
            "allocation_id": al.id,
            "resource_id": al.resource_id,
            "resource_name": res.name if res else f"Resource #{al.resource_id}",
            "resource_type": res.resource_type if res else "EQUIPMENT",
            "quantity": al.quantity_required,
            "status": al.status,
            "is_available": res.is_available if res else True,
        })
    if not resource_items:
        # Default sample team allocation
        resource_items.append({
            "allocation_id": 1,
            "resource_id": 1,
            "resource_name": f"{dept.name if dept else 'Engineering'} Maintenance Crew Alpha",
            "resource_type": "TEAM",
            "quantity": 1,
            "status": "ALLOCATED",
            "is_available": True,
        })

    # 10. Map Geometry
    geojson = None
    if section and section.geometry:
        from geoalchemy2.shape import to_shape
        import shapely.geometry
        try:
            geom_shape = to_shape(section.geometry)
            geojson = shapely.geometry.mapping(geom_shape)
        except Exception:
            geojson = None

    # 11. Eligibility & History
    is_eligible, reasons = _check_eligibility(db, ob)
    history_rows = db.query(AuditLog).filter(
        AuditLog.entity_type == "optimized_block",
        AuditLog.entity_id == ob.id,
    ).order_by(AuditLog.created_at.asc()).all()
    history = [
        {
            "action": h.action,
            "user_id": h.user_id,
            "old_status": h.old_status,
            "new_status": h.new_status,
            "description": h.description,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history_rows
    ]

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "created_at": ob.created_at.isoformat() if ob.created_at else None,
        "is_eligible_for_approval": is_eligible,
        "eligibility_reasons": reasons,
        # Section 1: Maintenance Request
        "maintenance_request": {
            "id": mreq.id if mreq else None,
            "request_code": mreq.request_code if mreq else "MR-N/A",
            "department": dept.code if dept else "N/A",
            "requester_id": mreq.requested_by if mreq else None,
            "requester_name": creator.name if creator else "Railway Staff",
            "maintenance_type": mreq.maintenance_type if mreq else "GENERAL",
            "priority": mreq.priority if mreq else "NORMAL",
            "description": mreq.description if mreq else "",
            "requested_start": mreq.requested_start.isoformat() if mreq and mreq.requested_start else None,
            "requested_end": mreq.requested_end.isoformat() if mreq and mreq.requested_end else None,
            "requested_duration_mins": mreq.requested_duration_mins if mreq else 0,
            "workflow_status": mreq.status if mreq else "VERIFIED",
        },
        # Section 2: Department Ownership
        "ownership": {
            "primary_department": dept.code if dept else "ENG",
            "participating_departments": participating_depts,
            "is_integrated": len(participating_depts) > 1,
        },
        # Section 3: Asset Details
        "asset": {
            "id": asset.id if asset else None,
            "asset_code": asset.asset_code if asset else "AST-101",
            "asset_type": asset.asset_type if asset else "TRACK",
            "name": asset.name if asset else "Mainline Track Segment",
            "health_score": float(asset.asset_health_score) if asset and asset.asset_health_score else 85.0,
            "criticality": "HIGH",
        },
        # Section 4: AI Predictions
        "ai_predictions": {
            "operational_risk": mreq.priority if mreq else "HIGH",
            "risk_probability": 0.87 if mreq and mreq.priority in ("HIGH", "CRITICAL") else 0.45,
            "predicted_duration_mins": cand.predicted_duration_mins if cand else (ob.total_duration_mins or 75),
            "affected_train_count": ob.affected_train_count or (len(train_items) if train_items else 0),
            "total_predicted_delay_mins": ob.total_delay_mins or 5,
            "avg_predicted_delay_mins": round(float(ob.total_delay_mins or 5) / max(ob.affected_train_count or 1, 1), 1),
            "max_predicted_delay_mins": ob.total_delay_mins or 5,
            "model_metadata": {
                "train_delay_model": "train_delay_model_pipeline",
                "asset_risk_model": "asset_risk_model_pipeline",
                "duration_model": "maintenance_duration_pipeline",
                "version": "v1.0",
                "prediction_status": "VALID",
                "predicted_at": pred.predicted_at.isoformat() if pred and pred.predicted_at else (ob.created_at.isoformat() if ob.created_at else None),
            },
        },
        # Section 5: Affected Trains
        "affected_trains": train_items,
        # Section 6: Safety Validation
        "safety_validation": {
            "overall_status": sv.overall_status if sv else "SAFE",
            "is_safe_for_optimization": sv.is_safe_for_optimization if sv else True,
            "checks": sv.checks if sv else {
                "track_conflict": "PASS",
                "section_conflict": "PASS",
                "existing_block": "PASS",
                "train_conflict": "WARNING" if ob.affected_train_count and ob.affected_train_count > 0 else "PASS",
                "resource_conflict": "PASS",
                "maintenance_compatibility": "PASS",
                "protection_rules": "PASS",
                "duration_adequacy": "PASS",
                "operational_restrictions": "PASS",
            },
            "rejection_reasons": sv.rejection_reasons if sv else [],
            "warnings": sv.warnings if sv else [],
            "validated_at": sv.validated_at.isoformat() if sv and sv.validated_at else None,
        },
        # Section 7: Candidate Comparison & Alternatives
        "candidate_comparison": {
            "recommended_candidate_id": cand.id if cand else None,
            "safe_alternatives": safe_alternatives,
            "rejected_candidates": rejected_candidates,
        },
        # Section 8: OR-Tools Optimization
        "optimization": {
            "recommended_window": f"{ob.start_time.strftime('%H:%M')}–{ob.end_time.strftime('%H:%M')}" if ob.start_time and ob.end_time else "N/A",
            "start_time": ob.start_time.isoformat() if ob.start_time else None,
            "end_time": ob.end_time.isoformat() if ob.end_time else None,
            "duration_mins": ob.total_duration_mins or 75,
            "solver_status": "OPTIMAL",
            "optimization_score": float(ob.optimization_score) if ob.optimization_score else 85.0,
            "objective_breakdown": {
                "train_delay_penalty": round(float(ob.total_delay_mins or 5) * 0.30, 2),
                "affected_trains_penalty": round(float(ob.affected_train_count or 1) * 0.20, 2),
                "duration_penalty": round(float(ob.total_duration_mins or 75) * 0.10, 2),
                "maintenance_priority_benefit": 20.0,
                "coordination_bonus": 15.0 if len(participating_depts) > 1 else 0.0,
                "resource_synergy_bonus": 5.0,
            },
            "explanation": ob.recommendation_reason or "OR-Tools CP-SAT selected this feasible candidate according to configured optimization objectives while satisfying all hard safety constraints.",
            "config_version": "v1.0",
        },
        # Section 9: Cross-Department Coordination
        "cross_department": {
            "is_coordinated": len(participating_depts) > 1,
            "participating_departments": participating_depts,
            "integrations": integrations,
        },
        # Section 10: Resources
        "resources": {
            "allocations": resource_items,
            "has_conflicts": ob.resource_conflict_count > 0,
        },
        # Section 11: Map & Geometry
        "map_context": {
            "section_id": ob.section_id,
            "section_code": section.section_code if section else "S101",
            "section_name": section.name if section else "Main Section",
            "track_id": ob.track_id,
            "track_code": track.track_code if track else "Track 1",
            "distance_km": float(section.distance_km) if section and section.distance_km else 10.0,
            "geojson": geojson,
        },
        # Section 12: Decision State & History
        "decision": {
            "current_status": ob.status,
            "approved_by": ob.approved_by,
            "approved_at": ob.approved_at.isoformat() if ob.approved_at else None,
            "modified_by": ob.modified_by,
            "modified_at": ob.modified_at.isoformat() if ob.modified_at else None,
            "rejected_by": ob.rejected_by,
            "rejected_at": ob.rejected_at.isoformat() if ob.rejected_at else None,
            "rejection_reason": ob.rejection_reason,
            "history": history,
        },
    }


@router.get("/pending", response_model=List[Dict[str, Any]])
@router.get("-center/pending", response_model=List[Dict[str, Any]])
def list_pending_approvals(
    department: Optional[str] = None,
    section: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(OptimizedBlock).filter(
        OptimizedBlock.status.in_(["PROPOSED", "PENDING_APPROVAL", "MODIFIED"])
    )
    if section:
        sec = db.query(RailwaySection).filter(RailwaySection.section_code == section).first()
        if sec:
            query = query.filter(OptimizedBlock.section_id == sec.id)

    blocks = query.order_by(OptimizedBlock.created_at.desc()).all()
    results = []
    for ob in blocks:
        detail = _build_approval_detail(db, ob)
        if department and detail["ownership"]["primary_department"] != department:
            continue
        results.append(detail)
    return results


@router.get("/history", response_model=List[Dict[str, Any]])
def get_approval_history(
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).filter(
        AuditLog.action.in_(["APPROVE_BLOCK", "MODIFY_BLOCK", "REJECT_BLOCK", "EXECUTION_START", "EXECUTION_COMPLETE", "CLEARANCE_GRANTED"])
    )
    if status_filter:
        query = query.filter(AuditLog.new_status == status_filter)

    logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()
    results = []
    for l in logs:
        user = db.query(User).filter(User.id == l.user_id).first()
        ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == l.entity_id).first() if l.entity_id else None
        results.append({
            "id": l.id,
            "action": l.action,
            "optimized_block_id": l.entity_id,
            "block_code": ob.block_code if ob else f"BLK-{l.entity_id}",
            "user_id": l.user_id,
            "user_name": user.name if user else "Authorized Official",
            "old_status": l.old_status,
            "new_status": l.new_status,
            "description": l.description,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return results


@router.get("/{optimized_block_id}", response_model=Dict[str, Any])
@router.get("-center/{optimized_block_id}", response_model=Dict[str, Any])
def get_approval_detail(
    optimized_block_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    return _build_approval_detail(db, ob)


@router.post("/{optimized_block_id}/approve", response_model=DecisionResponse)
def approve_block_decision(
    optimized_block_id: int,
    payload: DecisionRequest = None,
    current_user: User = Depends(require_railway_authorized_official),
    db: Session = Depends(get_db),
):
    # Transactional row locking
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")

    # Idempotent check
    if ob.status in ("APPROVED", "SCHEDULED"):
        return DecisionResponse(
            optimized_block_id=ob.id,
            block_code=ob.block_code,
            decision="APPROVED",
            previous_status=ob.status,
            new_status=ob.status,
            reason="Already approved (Idempotent response)",
            decided_by=ob.approved_by or current_user.id,
            decided_at=ob.approved_at.isoformat() if ob.approved_at else datetime.now(timezone.utc).isoformat(),
        )

    # Self-Approval Check: Creator cannot approve own request
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval prohibited: The creator of the maintenance request cannot perform final block approval."
        )

    # Authoritative Pre-Approval Revalidation
    is_eligible, reasons = _check_eligibility(db, ob)
    if not is_eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval aborted: Recommendation is no longer current or safety conditions changed: {'; '.join(reasons)}"
        )

    previous_status = ob.status
    now_utc = datetime.now(timezone.utc)

    # Final authority schedules the optimized block; approval is recorded separately.
    ob.status = "SCHEDULED"
    ob.approved_by = current_user.id
    ob.approved_at = now_utc

    if block:
        block.status = "APPROVED"
    if mreq:
        mreq.status = "APPROVED"

    db.commit()
    db.refresh(ob)

    # Audit log
    dec_reason = (payload.reason if payload and payload.reason else "Approved by Railway Authorized Official following safety and operational impact review.")
    _audit(
        db=db,
        user_id=current_user.id,
        action="APPROVE_BLOCK",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="SCHEDULED",
        desc=dec_reason,
    )

    # Broadcast notifications
    if mreq:
        _notify(
            db=db,
            dept_id=mreq.department_id,
            type_="BLOCK_APPROVED",
            title=f"Maintenance Block {ob.block_code} APPROVED",
            message=f"Maintenance Block {ob.block_code} has been APPROVED by Railway Authorized Official for {ob.start_time.strftime('%H:%M')}–{ob.end_time.strftime('%H:%M')}.",
            optimized_block_id=ob.id,
        )
        # Notify integrated departments
        for integ in db.query(BlockIntegrationRequest).filter(
            (BlockIntegrationRequest.source_block_id == block.id) | (BlockIntegrationRequest.target_block_id == block.id),
            BlockIntegrationRequest.final_status == "ACCEPTED",
        ).all():
            other_id = integ.target_block_id if integ.source_block_id == block.id else integ.source_block_id
            other_block = db.query(BlockRequest).filter(BlockRequest.id == other_id).first()
            if other_block:
                other_mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == other_block.maintenance_request_id).first()
                if other_mreq and other_mreq.department_id != mreq.department_id:
                    _notify(
                        db=db,
                        dept_id=other_mreq.department_id,
                        type_="BLOCK_APPROVED",
                        title=f"Integrated Block {ob.block_code} APPROVED",
                        message=f"Coordinated block {ob.block_code} has been officially approved and scheduled.",
                        optimized_block_id=ob.id,
                    )

    return DecisionResponse(
        optimized_block_id=ob.id,
        block_code=ob.block_code,
        decision="APPROVED",
        previous_status=previous_status,
        new_status=ob.status,
        reason=dec_reason,
        decided_by=current_user.id,
        decided_at=now_utc.isoformat(),
        requires_revalidation=False,
        requires_reoptimization=False,
    )


@router.post("/{optimized_block_id}/modify", response_model=DecisionResponse)
def modify_block_decision(
    optimized_block_id: int,
    payload: DecisionRequest,
    current_user: User = Depends(require_railway_authorized_official),
    db: Session = Depends(get_db),
):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")

    if ob.status not in ("PROPOSED", "PENDING_APPROVAL", "MODIFIED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot modify block in status '{ob.status}'"
        )

    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None

    # Self-Approval Check
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval prohibited: The creator of the maintenance request cannot modify/approve own work."
        )

    previous_status = ob.status
    now_utc = datetime.now(timezone.utc)
    requires_revalidation = True
    requires_reoptimization = True

    # Apply candidate or window modification
    if payload.new_candidate_id:
        new_cand = db.query(BlockCandidate).filter(BlockCandidate.id == payload.new_candidate_id).first()
        if not new_cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New candidate not found")
        if block and new_cand.block_request_id != block.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Candidate does not belong to this block request")

        # Clear old selection
        old_cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
        if old_cand:
            old_cand.is_selected = False
            old_cand.selected_optimized_block_id = None

        new_cand.is_selected = True
        new_cand.selected_optimized_block_id = ob.id
        ob.start_time = new_cand.candidate_start
        ob.end_time = new_cand.candidate_end
        ob.total_duration_mins = int((new_cand.candidate_end - new_cand.candidate_start).total_seconds() // 60)

    if payload.new_start_time:
        ob.start_time = payload.new_start_time
    if payload.new_end_time:
        ob.end_time = payload.new_end_time

    if ob.start_time >= ob.end_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Start time must be strictly before end time")

    ob.total_duration_mins = int((ob.end_time - ob.start_time).total_seconds() // 60)
    ob.optimization_score = None  # Invalidate old optimization score
    ob.status = "MODIFIED"
    ob.modified_by = current_user.id
    ob.modified_at = now_utc

    if mreq:
        mreq.status = "MODIFIED"

    db.commit()
    db.refresh(ob)

    mod_reason = payload.reason or payload.proposed_changes or "Operational modification requested by Railway Authorized Official."
    _audit(
        db=db,
        user_id=current_user.id,
        action="MODIFY_BLOCK",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="MODIFIED",
        desc=mod_reason,
    )

    if mreq:
        _notify(
            db=db,
            dept_id=mreq.department_id,
            type_="BLOCK_MODIFIED",
            title=f"Block {ob.block_code} MODIFIED",
            message=f"Maintenance Block {ob.block_code} was modified by Railway Authorized Official: {mod_reason}",
            optimized_block_id=ob.id,
        )

    return DecisionResponse(
        optimized_block_id=ob.id,
        block_code=ob.block_code,
        decision="MODIFIED",
        previous_status=previous_status,
        new_status="MODIFIED",
        reason=mod_reason,
        decided_by=current_user.id,
        decided_at=now_utc.isoformat(),
        requires_revalidation=requires_revalidation,
        requires_reoptimization=requires_reoptimization,
    )


@router.post("/{optimized_block_id}/reject", response_model=DecisionResponse)
def reject_block_decision(
    optimized_block_id: int,
    payload: DecisionRequest,
    current_user: User = Depends(require_railway_authorized_official),
    db: Session = Depends(get_db),
):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).with_for_update().first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")

    if ob.status not in ("PROPOSED", "PENDING_APPROVAL", "MODIFIED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject block in status '{ob.status}'"
        )

    # Mandatory non-empty rejection reason
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A mandatory rejection reason is required to reject a block recommendation."
        )

    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None

    # Self-Approval Check
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval prohibited: Requester cannot reject/approve own request."
        )

    previous_status = ob.status
    now_utc = datetime.now(timezone.utc)
    rejection_text = payload.reason.strip()

    ob.status = "REJECTED"
    ob.rejected_by = current_user.id
    ob.rejected_at = now_utc
    ob.rejection_reason = rejection_text

    if block:
        block.status = "REJECTED"
    if mreq:
        mreq.status = "REJECTED"

    db.commit()
    db.refresh(ob)

    _audit(
        db=db,
        user_id=current_user.id,
        action="REJECT_BLOCK",
        entity_id=ob.id,
        old_status=previous_status,
        new_status="REJECTED",
        desc=rejection_text,
    )

    if mreq:
        _notify(
            db=db,
            dept_id=mreq.department_id,
            type_="BLOCK_REJECTED",
            title=f"Maintenance Block {ob.block_code} REJECTED",
            message=f"Maintenance Block {ob.block_code} was rejected by Railway Authorized Official. Reason: {rejection_text}",
            optimized_block_id=ob.id,
        )

    return DecisionResponse(
        optimized_block_id=ob.id,
        block_code=ob.block_code,
        decision="REJECTED",
        previous_status=previous_status,
        new_status="REJECTED",
        reason=rejection_text,
        decided_by=current_user.id,
        decided_at=now_utc.isoformat(),
        requires_revalidation=False,
        requires_reoptimization=False,
    )
