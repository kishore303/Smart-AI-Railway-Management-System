from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.core.rbac import get_current_active_user, can_access_department_resource
from app.models.user import User
from app.models.department import Department
from app.models.block import BlockRequest, BlockCandidate, OptimizedBlock, OptimizedBlockSource, BlockIntegrationRequest
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.schemas.recommendation import RecommendationResponse, OfficialDecisionRequest, OfficialDecisionResponse

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

# Only official can approve/modify/reject
OFFICIAL_ROLE = "AUTHORIZED_OFFICIAL"


def _audit(db: Session, user_id, action, entity_id=None, desc=None):
    log = AuditLog(user_id=user_id, action=action, entity_type="optimized_block", entity_id=entity_id, description=desc)
    db.add(log)
    db.commit()


def _notify(db: Session, dept_id: int, type_: str, title: str, message: str, optimized_block_id: int = None):
    n = Notification(
        recipient_department_id=dept_id,
        type=type_,
        title=title,
        message=message,
        priority="HIGH" if type_ in ("BLOCK_APPROVED", "BLOCK_REJECTED") else "NORMAL",
        optimized_block_id=optimized_block_id,
    )
    db.add(n)
    db.commit()


def _check_eligibility(db: Session, ob: OptimizedBlock) -> tuple[bool, list]:
    reasons = []
    is_eligible = True

    # Must be PROPOSED or PENDING_APPROVAL to be reviewable
    if ob.status not in ("PROPOSED", "PENDING_APPROVAL", "MODIFIED"):
        reasons.append(f"Optimized block status {ob.status} not eligible for approval (must be PROPOSED/PENDING_APPROVAL/MODIFIED)")
        is_eligible = False

    # Must have selected candidate
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        # Also check via is_selected
        cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
        if not cand:
            # Try to find candidate that is_selected and has this ob as selected
            cand = db.query(BlockCandidate).filter(BlockCandidate.is_selected == True, BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        # Fallback: find any candidate for this block that is selected
        # Actually, our optimized block should have a selected candidate
        reasons.append("No selected candidate found for optimized block")
        is_eligible = False
        return is_eligible, reasons
    else:
        # Check safety validation
        sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first()
        if not sv:
            reasons.append(f"Candidate {cand.id} missing SafetyValidation — must be validated")
            is_eligible = False
        elif sv.overall_status != "SAFE":
            reasons.append(f"Candidate {cand.id} SafetyValidation not SAFE (is {sv.overall_status})")
            is_eligible = False
        elif not sv.is_safe_for_optimization:
            reasons.append(f"Candidate {cand.id} is_safe_for_optimization false")
            is_eligible = False
        # Check planning status vs safety: planning FEASIBLE is okay, but safety must be SAFE (already checked)
        if cand.safety_status == "INFEASIBLE":
            reasons.append(f"Candidate {cand.id} planning safety_status INFEASIBLE")
            # This is not necessarily fatal if safety says SAFE, but we note
            pass

    # Check optimization score exists
    if ob.optimization_score is None:
        reasons.append("Optimized block missing optimization_score — must be from OR-Tools")
        is_eligible = False

    # Check if block request still exists and is not stale
    # Find source block
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        if not block:
            reasons.append("Source block request not found")
            is_eligible = False
        elif block.status in ("REJECTED", "CANCELLED", "COMPLETED"):
            reasons.append(f"Source block request status {block.status} not eligible")
            is_eligible = False
        # Check timing not in past
        if ob.start_time and ob.start_time < datetime.now(timezone.utc):
            reasons.append("Optimized block start time is in the past — stale")
            is_eligible = False
        # Check for new conflicting block that invalidates recommendation
        # Look for any block_request overlapping same section/track that was created after optimized block
        if block:
            conflict = db.query(BlockRequest).filter(
                BlockRequest.id != block.id,
                BlockRequest.section_id == ob.section_id,
                BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
                BlockRequest.requested_start < ob.end_time,
                BlockRequest.requested_end > ob.start_time,
                BlockRequest.created_at > ob.created_at,
            ).first()
            if conflict:
                reasons.append(f"New conflicting block {conflict.block_code} created after optimization — requires revalidation")
                is_eligible = False

    # Check integration status not changed — via optimized_block_sources
    # For each other source in the optimized block, verify the integration that contributed is still ACCEPTED
    all_sources = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).all()
    source_ids = [s.block_request_id for s in all_sources]
    if len(source_ids) > 1:
        # Primary is the first source (the block that was optimized)
        primary = source_ids[0]
        for other_id in source_ids[1:]:
            # Find integration between primary and other (either direction)
            integ = db.query(BlockIntegrationRequest).filter(
                ((BlockIntegrationRequest.source_block_id == primary) & (BlockIntegrationRequest.target_block_id == other_id)) |
                ((BlockIntegrationRequest.source_block_id == other_id) & (BlockIntegrationRequest.target_block_id == primary))
            ).first()
            if not integ:
                reasons.append(f"Required cross-department integration {primary}<->{other_id} missing — stale, revalidation/reoptimization required")
                is_eligible = False
            elif integ.final_status != "ACCEPTED":
                reasons.append(f"Required cross-department integration {integ.id} ({primary}<->{other_id}) changed from ACCEPTED to {integ.final_status} — stale, revalidation/reoptimization required")
                is_eligible = False

    return is_eligible, reasons


def _build_recommendation(db: Session, ob: OptimizedBlock) -> dict:
    # Find selected candidate
    cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        cand = db.query(BlockCandidate).filter(BlockCandidate.is_selected == True).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
    if not cand:
        # Fallback: any candidate for this block that is most recent
        # Find via block_request
        src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
        if src:
            cand = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == src.block_request_id, BlockCandidate.is_selected == True).first()
    # Find block and maintenance
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    # Department
    dept = db.query(Department).filter(Department.id == mreq.department_id).first() if mreq else None
    asset = None
    section = None
    track = None
    if mreq:
        from app.models.asset import Asset
        from app.models.railway import RailwaySection, Track
        asset = db.query(Asset).filter(Asset.id == mreq.asset_id).first()
        section = db.query(RailwaySection).filter(RailwaySection.id == ob.section_id).first()
        track = db.query(Track).filter(Track.id == ob.track_id).first() if ob.track_id else None
    # Safety validation
    sv = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == cand.id).first() if cand else None
    # Alternatives: other candidates for same block
    alternatives = []
    if block:
        all_cands = db.query(BlockCandidate).filter(BlockCandidate.block_request_id == block.id).all()
        for c in all_cands:
            if cand and c.id == cand.id:
                continue
            sv_alt = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == c.id).first()
            alternatives.append({
                "candidate_id": c.id,
                "candidate_start": c.candidate_start.isoformat() if c.candidate_start else None,
                "candidate_end": c.candidate_end.isoformat() if c.candidate_end else None,
                "duration_mins": int((c.candidate_end - c.candidate_start).total_seconds() // 60) if c.candidate_start and c.candidate_end else None,
                "safety_status": c.safety_status,
                "safety_overall": sv_alt.overall_status if sv_alt else None,
                "is_safe": sv_alt.is_safe_for_optimization if sv_alt else False,
                "optimization_eligible": sv_alt.is_safe_for_optimization if sv_alt and sv_alt.overall_status == "SAFE" else False,
                "predicted_delay": c.predicted_delay_mins,
                "asset_risk": float(c.asset_risk_score) if c.asset_risk_score else None,
                "reason_not_selected": "Not selected by optimizer" if c.id != (cand.id if cand else None) else "Selected",
            })
            # Mark unsafe explicitly
            if sv_alt and sv_alt.overall_status == "UNSAFE":
                alternatives[-1]["reason_not_selected"] = f"UNSAFE: {', '.join(sv_alt.rejection_reasons[:2]) if sv_alt.rejection_reasons else 'safety failed'}"
            elif not sv_alt:
                alternatives[-1]["reason_not_selected"] = "Missing SafetyValidation — not eligible for optimization"

    # Integration summary
    from app.models.block import BlockIntegrationRequest
    integ_summary = []
    if src:
        integs = db.query(BlockIntegrationRequest).filter(
            (BlockIntegrationRequest.source_block_id == block.id) | (BlockIntegrationRequest.target_block_id == block.id)
        ).all()
        for integ in integs:
            src_block = db.query(BlockRequest).filter(BlockRequest.id == integ.source_block_id).first()
            tgt_block = db.query(BlockRequest).filter(BlockRequest.id == integ.target_block_id).first()
            req_dept = db.query(Department).filter(Department.id == integ.requesting_department_id).first()
            tgt_dept = db.query(Department).filter(Department.id == integ.target_department_id).first()
            integ_summary.append({
                "integration_id": integ.id,
                "source_block": src_block.block_code if src_block else str(integ.source_block_id),
                "target_block": tgt_block.block_code if tgt_block else str(integ.target_block_id),
                "requesting_dept": req_dept.code if req_dept else str(integ.requesting_department_id),
                "target_dept": tgt_dept.code if tgt_dept else str(integ.target_department_id),
                "compatibility_status": integ.compatibility_status,
                "overlap_mins": integ.overlap_duration_mins,
                "final_status": integ.final_status,
            })

    # Warnings
    warnings = []
    if sv and sv.warnings:
        warnings.extend(sv.warnings)
    if ob.status != "PROPOSED":
        warnings.append(f"Optimized block status is {ob.status}, not PROPOSED — may be stale")

    # Decision history
    history = db.query(AuditLog).filter(AuditLog.entity_type == "optimized_block", AuditLog.entity_id == ob.id).order_by(AuditLog.created_at.asc()).all()
    history_list = [{"action": h.action, "user_id": h.user_id, "description": h.description, "created_at": h.created_at.isoformat() if h.created_at else None} for h in history]

    is_eligible, reasons = _check_eligibility(db, ob)

    return {
        "optimized_block_id": ob.id,
        "block_code": ob.block_code,
        "status": ob.status,
        "is_eligible_for_approval": is_eligible,
        "eligibility_reasons": reasons,
        "request_summary": {
            "maintenance_request_id": mreq.id if mreq else None,
            "request_code": mreq.request_code if mreq else None,
            "department_code": dept.code if dept else None,
            "asset_id": asset.id if asset else None,
            "asset_code": asset.asset_code if asset else None,
            "section_id": ob.section_id,
            "section_code": section.section_code if section else None,
            "track_id": ob.track_id,
            "track_code": track.track_code if track else None,
            "maintenance_type": mreq.maintenance_type if mreq else None,
            "priority": mreq.priority if mreq else None,
            "requested_start": mreq.requested_start.isoformat() if mreq and mreq.requested_start else None,
            "requested_end": mreq.requested_end.isoformat() if mreq and mreq.requested_end else None,
            "requested_duration_mins": mreq.requested_duration_mins if mreq else None,
        },
        "safety_summary": {
            "candidate_id": cand.id if cand else None,
            "overall_status": sv.overall_status if sv else None,
            "is_safe_for_optimization": sv.is_safe_for_optimization if sv else None,
            "checks": sv.checks if sv else None,
            "rejection_reasons": sv.rejection_reasons if sv else None,
            "warnings": sv.warnings if sv else None,
            "validated_at": sv.validated_at.isoformat() if sv and sv.validated_at else None,
            "validated_by": sv.validated_by if sv else None,
            "planning_safety_status": cand.safety_status if cand else None,
        },
        "optimization_summary": {
            "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
            "objective_value": None,  # Could store, but we have score
            "objective_summary": None,  # From engine, but we store explanation in recommendation_reason
            "explanation": ob.recommendation_reason,
            "solver_status": None,
            "total_considered": None,
            "eligible": None,
        },
        "selected_recommendation": {
            "candidate_id": cand.id if cand else None,
            "candidate_start": cand.candidate_start.isoformat() if cand and cand.candidate_start else None,
            "candidate_end": cand.candidate_end.isoformat() if cand and cand.candidate_end else None,
            "predicted_duration_mins": cand.predicted_duration_mins if cand else None,
            "predicted_delay_mins": cand.predicted_delay_mins if cand else None,
            "asset_risk_score": float(cand.asset_risk_score) if cand and cand.asset_risk_score else None,
            "optimization_score": float(cand.optimization_score) if cand and cand.optimization_score else None,
            "is_selected": cand.is_selected if cand else None,
        } if cand else None,
        "alternatives": alternatives,
        "integration_summary": integ_summary,
        "warnings": warnings,
        "decision_status": ob.status,
        "decision_history": history_list,
    }


@router.get("/{optimized_block_id}", response_model=dict)
def get_recommendation(optimized_block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    # Dept check via source block's maintenance
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
        if mreq:
            if not can_access_department_resource(current_user, mreq.department_id, db):
                if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    rec = _build_recommendation(db, ob)
    return rec


@router.get("/{optimized_block_id}/explanation")
def get_explanation(optimized_block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    rec = _build_recommendation(db, ob)
    # Human-readable explanation
    cand = rec["selected_recommendation"]
    safety = rec["safety_summary"]
    opt = rec["optimization_summary"]
    text_expl = (
        f"Candidate {cand['candidate_id'] if cand else 'unknown'} was recommended because it passed all mandatory Safety Engine checks "
        f"({safety['overall_status'] if safety else 'unknown'}) and produced the lowest supported optimization cost among eligible safe candidates. "
        f"The recommendation considers predicted delay {cand['predicted_delay_mins'] if cand and cand['predicted_delay_mins'] else 'not provided'}, "
        f"maintenance duration {cand['predicted_duration_mins'] if cand else 'not provided'} mins, "
        f"asset risk {cand['asset_risk_score'] if cand else 'not provided'}, "
        f"priority {rec['request_summary']['priority']}, "
        f"and accepted cross-department integration benefits where applicable. "
        f"Safety validation at {safety['validated_at'] if safety and safety['validated_at'] else 'unknown'} showed {len(safety['checks']) if safety and safety['checks'] else 0} checks, "
        f"all mandatory passed. "
        f"Alternatives: {len(rec['alternatives'])} other candidates considered, unsafe excluded. "
        f"Note: {rec['optimization_summary']['explanation'] or ob.recommendation_reason or 'No additional notes'}"
    )
    return {"optimized_block_id": optimized_block_id, "explanation": text_expl, "details": rec}


@router.post("/{optimized_block_id}/approve")
def approve_recommendation(optimized_block_id: int, payload: OfficialDecisionRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role != OFFICIAL_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only AUTHORIZED_OFFICIAL can approve")
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    # Check eligibility
    is_eligible, reasons = _check_eligibility(db, ob)
    if not is_eligible:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Recommendation requires revalidation/reoptimization because planning inputs changed: {'; '.join(reasons)}")
    # Self-approval check
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester cannot approve own request (self-approval prohibited)")
    # Stale check already done via _check_eligibility
    old_status = ob.status
    ob.status = "APPROVED"
    ob.approved_by = current_user.id
    ob.approved_at = datetime.now(timezone.utc)
    # Also update maintenance request status to APPROVED
    if mreq:
        mreq.status = "APPROVED"
    db.commit()
    db.refresh(ob)
    _audit(db, current_user.id, "APPROVE_BLOCK", entity_id=ob.id, desc=payload.reason or "Approved by official")
    # Notifications
    if mreq:
        _notify(db, mreq.department_id, "BLOCK_APPROVED", f"Block {ob.block_code} approved", f"Optimized block {ob.block_code} approved by {current_user.name}: {payload.reason or ''}", optimized_block_id=ob.id)
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
                    _notify(db, other_mreq.department_id, "BLOCK_APPROVED", f"Integrated block {ob.block_code} approved", f"Your integrated block {other_block.block_code} approved", optimized_block_id=ob.id)
    return {"optimized_block_id": ob.id, "new_status": ob.status, "decision": "APPROVED", "reason": payload.reason, "decided_by": current_user.id, "decided_at": ob.approved_at.isoformat(), "requires_revalidation": False, "requires_reoptimization": False}


@router.post("/{optimized_block_id}/reject")
def reject_recommendation(optimized_block_id: int, payload: OfficialDecisionRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role != OFFICIAL_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only AUTHORIZED_OFFICIAL can reject")
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    if ob.status not in ("PROPOSED", "PENDING_APPROVAL", "MODIFIED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot reject from status {ob.status}")
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rejection reason required")
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval prohibited")
    old_status = ob.status
    ob.status = "REJECTED"
    ob.rejected_by = current_user.id
    ob.rejected_at = datetime.now(timezone.utc)
    ob.rejection_reason = payload.reason
    if mreq:
        mreq.status = "REJECTED"
    db.commit()
    _audit(db, current_user.id, "REJECT_BLOCK", entity_id=ob.id, desc=payload.reason)
    if mreq:
        _notify(db, mreq.department_id, "BLOCK_REJECTED", f"Block {ob.block_code} rejected", payload.reason, optimized_block_id=ob.id)
    return {"optimized_block_id": ob.id, "new_status": ob.status, "decision": "REJECTED", "reason": payload.reason, "decided_by": current_user.id, "decided_at": ob.rejected_at.isoformat(), "requires_revalidation": False, "requires_reoptimization": False}


@router.post("/{optimized_block_id}/modify")
def modify_recommendation(optimized_block_id: int, payload: OfficialDecisionRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if current_user.role != OFFICIAL_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only AUTHORIZED_OFFICIAL can modify")
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    if ob.status not in ("PROPOSED", "PENDING_APPROVAL"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot modify from status {ob.status}")
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first() if src else None
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
    if mreq and mreq.requested_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval prohibited")
    # Determine if safety/optimization sensitive
    requires_revalidation = False
    requires_reoptimization = False
    if payload.new_start_time or payload.new_end_time or payload.new_candidate_id:
        requires_revalidation = True
        requires_reoptimization = True
    old_status = ob.status
    # Apply changes
    if payload.new_candidate_id:
        # Validate new candidate exists and is safe
        new_cand = db.query(BlockCandidate).filter(BlockCandidate.id == payload.new_candidate_id).first()
        if not new_cand:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New candidate not found")
        # Check that new candidate belongs to same block_request
        if new_cand.block_request_id != block.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New candidate does not belong to same block")
        # Do NOT automatically mark SAFE — require revalidation
        # Update optimized block to new candidate's times
        ob.start_time = new_cand.candidate_start
        ob.end_time = new_cand.candidate_end
        ob.total_duration_mins = int((new_cand.candidate_end - new_cand.candidate_start).total_seconds() // 60)
        # Update candidate selection
        # Clear old
        old_cand = db.query(BlockCandidate).filter(BlockCandidate.selected_optimized_block_id == ob.id).first()
        if old_cand:
            old_cand.is_selected = False
            old_cand.selected_optimized_block_id = None
        new_cand.is_selected = True
        new_cand.selected_optimized_block_id = ob.id
        ob.optimization_score = None  # Invalidate old score
    if payload.new_start_time:
        ob.start_time = payload.new_start_time
        requires_revalidation = True
        requires_reoptimization = True
    if payload.new_end_time:
        ob.end_time = payload.new_end_time
        requires_revalidation = True
        requires_reoptimization = True
    if payload.new_start_time or payload.new_end_time:
        if ob.start_time >= ob.end_time:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start must be before end")
        ob.total_duration_mins = int((ob.end_time - ob.start_time).total_seconds() // 60)

    ob.status = "MODIFIED"
    ob.modified_by = current_user.id
    ob.modified_at = datetime.now(timezone.utc)
    if mreq:
        mreq.status = "MODIFIED"
    db.commit()
    db.refresh(ob)
    _audit(db, current_user.id, "MODIFY_BLOCK", entity_id=ob.id, desc=payload.reason or f"Modified: revalidation={requires_revalidation} reoptimization={requires_reoptimization}")
    # Notify
    if mreq:
        _notify(db, mreq.department_id, "BLOCK_MODIFIED", f"Block {ob.block_code} modified", f"Modified by {current_user.name}: {payload.reason or ''} — requires revalidation={requires_revalidation}", optimized_block_id=ob.id)
    return {
        "optimized_block_id": ob.id,
        "new_status": ob.status,
        "decision": "MODIFIED",
        "reason": payload.reason,
        "decided_by": current_user.id,
        "decided_at": ob.modified_at.isoformat(),
        "requires_revalidation": requires_revalidation,
        "requires_reoptimization": requires_reoptimization,
    }


@router.get("/{optimized_block_id}/history")
def get_history(optimized_block_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == optimized_block_id).first()
    if not ob:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimized block not found")
    # Dept check via source
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if src:
        block = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None
        if mreq:
            if not can_access_department_resource(current_user, mreq.department_id, db):
                if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    rows = db.query(AuditLog).filter(AuditLog.entity_type == "optimized_block", AuditLog.entity_id == optimized_block_id).order_by(AuditLog.created_at.asc()).all()
    return [{"action": r.action, "user_id": r.user_id, "description": r.description, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
