from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import List, Dict

from app.models.block import BlockCandidate, BlockRequest, OptimizedBlock
from app.models.maintenance import MaintenanceRequest
from app.models.train import TrainSchedule
from app.models.resource import Resource
from app.models.block import BlockResourceAllocation
from app.models.incident import Incident


def _check_timing(candidate: BlockCandidate, block: BlockRequest, mreq: MaintenanceRequest) -> Dict:
    if candidate.candidate_start >= candidate.candidate_end:
        return {"check": "TIMING", "status": "FAIL", "reason": "candidate_start must be before candidate_end", "severity": "mandatory"}
    duration = int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60)
    required = mreq.requested_duration_mins or candidate.predicted_duration_mins
    if required and duration < required:
        return {"check": "TIMING", "status": "FAIL", "reason": f"candidate duration {duration} mins < required {required} mins", "severity": "mandatory"}
    if duration <= 0:
        return {"check": "TIMING", "status": "FAIL", "reason": "invalid duration", "severity": "mandatory"}
    return {"check": "TIMING", "status": "PASS", "reason": f"window valid {duration} mins", "severity": "mandatory"}


def _check_track_conflict(candidate: BlockCandidate, db: Session) -> Dict:
    # Same section+track overlapping active block_requests / optimized_blocks
    # Exclude the candidate's own block and its optimized block (to avoid self-conflict after optimization)
    from app.models.block import OptimizedBlockSource
    q = db.query(BlockRequest).filter(
        BlockRequest.id != candidate.block_request_id,
        BlockRequest.section_id == candidate.section_id,
        BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        BlockRequest.requested_start < candidate.candidate_end,
        BlockRequest.requested_end > candidate.candidate_start,
    )
    if candidate.track_id:
        q = q.filter((BlockRequest.track_id == candidate.track_id) | (BlockRequest.track_id.is_(None)))
    if q.first():
        return {"check": "TRACK_CONFLICT", "status": "FAIL", "reason": "same track overlapping existing block request", "severity": "mandatory"}
    # For optimized blocks, exclude those that are linked to this candidate's block (self)
    q2 = db.query(OptimizedBlock).filter(
        OptimizedBlock.section_id == candidate.section_id,
        OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        OptimizedBlock.start_time < candidate.candidate_end,
        OptimizedBlock.end_time > candidate.candidate_start,
    )
    if candidate.track_id:
        q2 = q2.filter((OptimizedBlock.track_id == candidate.track_id) | (OptimizedBlock.track_id.is_(None)))
    # Exclude self's optimized block
    # Find optimized blocks that are linked to this candidate's block
    from app.models.block import BlockRequest as BR
    # Get all optimized block ids linked to this candidate's block
    linked_obs = db.query(OptimizedBlockSource.optimized_block_id).filter(OptimizedBlockSource.block_request_id == candidate.block_request_id).all()
    linked_ids = [r[0] for r in linked_obs]
    if linked_ids:
        q2 = q2.filter(OptimizedBlock.id.notin_(linked_ids))
    if q2.first():
        return {"check": "TRACK_CONFLICT", "status": "FAIL", "reason": "same track overlapping optimized block", "severity": "mandatory"}
    return {"check": "TRACK_CONFLICT", "status": "PASS", "reason": "no track conflict", "severity": "mandatory"}


def _check_section_conflict(candidate: BlockCandidate, db: Session) -> Dict:
    # Section-level: any block on same section where track is null (whole section) overlapping
    q = db.query(BlockRequest).filter(
        BlockRequest.id != candidate.block_request_id,
        BlockRequest.section_id == candidate.section_id,
        BlockRequest.track_id.is_(None),
        BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        BlockRequest.requested_start < candidate.candidate_end,
        BlockRequest.requested_end > candidate.candidate_start,
    )
    if q.first():
        return {"check": "SECTION_CONFLICT", "status": "FAIL", "reason": "section-level block overlapping", "severity": "mandatory"}
    return {"check": "SECTION_CONFLICT", "status": "PASS", "reason": "no section conflict", "severity": "mandatory"}


def _check_train_conflict(candidate: BlockCandidate, db: Session) -> Dict:
    # Train movement overlapping same section/track/time
    q = db.query(TrainSchedule).filter(
        TrainSchedule.section_id == candidate.section_id,
        TrainSchedule.entry_time < candidate.candidate_end,
        TrainSchedule.exit_time > candidate.candidate_start,
    )
    if candidate.track_id:
        q = q.filter((TrainSchedule.track_id == candidate.track_id) | (TrainSchedule.track_id.is_(None)))
    trains = q.limit(5).all()
    if trains:
        return {"check": "TRAIN_CONFLICT", "status": "FAIL", "reason": f"{len(trains)} train(s) scheduled overlapping candidate window", "severity": "mandatory"}
    # No trains found — check if any train data exists at all for section
    any_train = db.query(TrainSchedule).filter(TrainSchedule.section_id == candidate.section_id).first()
    if not any_train:
        return {"check": "TRAIN_CONFLICT", "status": "PASS", "reason": "no train schedule data for section — no known conflict (warning: data missing)", "severity": "mandatory", "warning": "train data missing for section"}
    return {"check": "TRAIN_CONFLICT", "status": "PASS", "reason": "no train movement conflict", "severity": "mandatory"}


def _check_adjacent_fouling(candidate: BlockCandidate, db: Session) -> Dict:
    # Same section, different track overlapping — fouling risk
    if not candidate.track_id:
        return {"check": "ADJACENT_FOULING", "status": "PASS", "reason": "no specific track — cannot assess fouling, assumed section-level", "severity": "warning"}
    q = db.query(BlockRequest).filter(
        BlockRequest.id != candidate.block_request_id,
        BlockRequest.section_id == candidate.section_id,
        BlockRequest.track_id != candidate.track_id,
        BlockRequest.track_id.isnot(None),
        BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        BlockRequest.requested_start < candidate.candidate_end,
        BlockRequest.requested_end > candidate.candidate_start,
    )
    adj = q.first()
    if adj:
        return {"check": "ADJACENT_FOULING", "status": "FAIL", "reason": f"adjacent track {adj.track_id} has overlapping block {adj.block_code} — fouling risk, protection required", "severity": "mandatory"}
    return {"check": "ADJACENT_FOULING", "status": "PASS", "reason": "no adjacent track conflict", "severity": "mandatory"}


def _check_resource_conflict(candidate: BlockCandidate, block: BlockRequest, db: Session) -> Dict:
    # Exclude self's optimized block as well
    from app.models.block import OptimizedBlockSource
    linked_obs = db.query(OptimizedBlockSource.optimized_block_id).filter(OptimizedBlockSource.block_request_id == candidate.block_request_id).all()
    linked_ids = [r[0] for r in linked_obs]
    overlapping = db.query(OptimizedBlock).filter(
        OptimizedBlock.section_id == candidate.section_id,
        OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
        OptimizedBlock.start_time < candidate.candidate_end,
        OptimizedBlock.end_time > candidate.candidate_start,
    )
    if linked_ids:
        overlapping = overlapping.filter(OptimizedBlock.id.notin_(linked_ids))
    overlapping = overlapping.all()
    for ob in overlapping:
        allocs = db.query(BlockResourceAllocation).filter(
            BlockResourceAllocation.block_id == ob.id,
            BlockResourceAllocation.allocated_from < candidate.candidate_end,
            BlockResourceAllocation.allocated_until > candidate.candidate_start,
            BlockResourceAllocation.status == "ALLOCATED",
        ).first()
        if allocs:
            return {"check": "RESOURCE_CONFLICT", "status": "FAIL", "reason": f"resource {allocs.resource_id} allocated to overlapping optimized block {ob.block_code}", "severity": "mandatory"}
    any_alloc = db.query(BlockResourceAllocation).first()
    if not any_alloc:
        return {"check": "RESOURCE_CONFLICT", "status": "PASS", "reason": "no resource allocation data — no known conflict", "severity": "mandatory", "warning": "resource data missing"}
    return {"check": "RESOURCE_CONFLICT", "status": "PASS", "reason": "no resource conflict", "severity": "mandatory"}


def _check_maintenance_compatibility(candidate: BlockCandidate, block: BlockRequest, mreq: MaintenanceRequest, db: Session) -> Dict:
    # Check overlapping blocks from different departments without accepted integration
    from app.models.block import BlockIntegrationRequest

    overlapping = db.query(BlockRequest).filter(
        BlockRequest.id != block.id,
        BlockRequest.section_id == candidate.section_id,
        BlockRequest.requested_start < candidate.candidate_end,
        BlockRequest.requested_end > candidate.candidate_start,
        BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
    ).all()
    for ob in overlapping:
        omreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == ob.maintenance_request_id).first()
        if omreq and omreq.department_id != mreq.department_id:
            # Check if accepted integration exists between these blocks
            integ = db.query(BlockIntegrationRequest).filter(
                ((BlockIntegrationRequest.source_block_id == block.id) & (BlockIntegrationRequest.target_block_id == ob.id) |
                 (BlockIntegrationRequest.source_block_id == ob.id) & (BlockIntegrationRequest.target_block_id == block.id)),
                BlockIntegrationRequest.final_status == "ACCEPTED",
            ).first()
            if not integ:
                return {"check": "MAINTENANCE_COMPATIBILITY", "status": "FAIL", "reason": f"overlapping block {ob.block_code} from different department {omreq.department_id} without accepted integration", "severity": "mandatory"}
    return {"check": "MAINTENANCE_COMPATIBILITY", "status": "PASS", "reason": "no incompatible maintenance", "severity": "mandatory"}


def _check_protection(candidate: BlockCandidate, block: BlockRequest, mreq: MaintenanceRequest) -> Dict:
    if not block.block_type:
        return {"check": "PROTECTION_REQUIREMENT", "status": "FAIL", "reason": "missing block_type — protection requirement unknown", "severity": "mandatory"}
    # Also check description for protection keyword? For demo, require block_type
    return {"check": "PROTECTION_REQUIREMENT", "status": "PASS", "reason": f"block_type {block.block_type} provided", "severity": "mandatory"}


def _check_operational(candidate: BlockCandidate) -> Dict:
    # Check if candidate is in past
    now = datetime.now(timezone.utc)
    if candidate.candidate_start < now:
        return {"check": "OPERATIONAL_RESTRICTION", "status": "FAIL", "reason": "candidate starts in the past", "severity": "mandatory"}
    # Check duration not excessive (>24h maybe)
    dur = int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60)
    if dur > 1440:
        return {"check": "OPERATIONAL_RESTRICTION", "status": "FAIL", "reason": f"duration {dur} mins exceeds operational limit 1440", "severity": "mandatory"}
    return {"check": "OPERATIONAL_RESTRICTION", "status": "PASS", "reason": "operational timing valid", "severity": "mandatory"}


def _check_emergency(candidate: BlockCandidate, db: Session) -> Dict:
    # Check open incidents in same section/track
    q = db.query(Incident).filter(
        Incident.section_id == candidate.section_id,
        Incident.response_status != "CLEARED",
    )
    if candidate.track_id:
        q = q.filter((Incident.track_id == candidate.track_id) | (Incident.track_id.is_(None)))
    inc = q.first()
    if inc:
        return {"check": "EMERGENCY_RESTRICTION", "status": "FAIL", "reason": f"open incident {inc.incident_code} in section {candidate.section_id}", "severity": "mandatory"}
    # No incident data? Check if any incident exists
    any_inc = db.query(Incident).first()
    if not any_inc:
        return {"check": "EMERGENCY_RESTRICTION", "status": "PASS", "reason": "no open incidents — no emergency restriction (no incident data)", "severity": "mandatory", "warning": "incident data missing"}
    return {"check": "EMERGENCY_RESTRICTION", "status": "PASS", "reason": "no emergency restriction", "severity": "mandatory"}


CHECKS = [
    ("TIMING", _check_timing),
    ("TRACK_CONFLICT", _check_track_conflict),
    ("SECTION_CONFLICT", _check_section_conflict),
    ("TRAIN_CONFLICT", _check_train_conflict),
    ("ADJACENT_FOULING", _check_adjacent_fouling),
    ("RESOURCE_CONFLICT", _check_resource_conflict),
    ("MAINTENANCE_COMPATIBILITY", _check_maintenance_compatibility),
    ("PROTECTION_REQUIREMENT", _check_protection),
    ("OPERATIONAL_RESTRICTION", _check_operational),
    ("EMERGENCY_RESTRICTION", _check_emergency),
]


def validate_candidate(candidate: BlockCandidate, db: Session) -> Dict:
    block = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()
    mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first() if block else None

    checks = []
    rejection_reasons = []
    warnings = []

    for name, func in CHECKS:
        try:
            if name == "TIMING":
                res = func(candidate, block, mreq)
            elif name in ("TRACK_CONFLICT", "SECTION_CONFLICT", "TRAIN_CONFLICT", "ADJACENT_FOULING", "RESOURCE_CONFLICT"):
                res = func(candidate, db) if name not in ("RESOURCE_CONFLICT",) else func(candidate, block, db)
                # Resource and adjacent need block
                if name == "RESOURCE_CONFLICT":
                    res = _check_resource_conflict(candidate, block, db)
                elif name == "ADJACENT_FOULING":
                    res = _check_adjacent_fouling(candidate, db)
                elif name == "TRAIN_CONFLICT":
                    res = _check_train_conflict(candidate, db)
                elif name == "TRACK_CONFLICT":
                    res = _check_track_conflict(candidate, db)
                elif name == "SECTION_CONFLICT":
                    res = _check_section_conflict(candidate, db)
            elif name == "MAINTENANCE_COMPATIBILITY":
                res = _check_maintenance_compatibility(candidate, block, mreq, db)
            elif name == "PROTECTION_REQUIREMENT":
                res = _check_protection(candidate, block, mreq)
            elif name == "OPERATIONAL_RESTRICTION":
                res = _check_operational(candidate)
            elif name == "EMERGENCY_RESTRICTION":
                res = _check_emergency(candidate, db)
            else:
                res = {"check": name, "status": "PASS", "reason": "not implemented", "severity": "warning"}
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            res = {"check": name, "status": "FAIL", "reason": f"check error: {e}", "severity": "mandatory"}

        checks.append(res)
        if res["status"] == "FAIL" and res.get("severity") == "mandatory":
            rejection_reasons.append(f"{res['check']}: {res['reason']}")
        if "warning" in res:
            warnings.append(f"{res['check']}: {res['warning']}")

    # Overall: SAFE only if no mandatory FAIL
    has_fail = any(c["status"] == "FAIL" and c.get("severity") == "mandatory" for c in checks)
    overall = "UNSAFE" if has_fail else "SAFE"
    is_safe = not has_fail

    return {
        "candidate_id": candidate.id,
        "block_request_id": candidate.block_request_id,
        "overall_status": overall,
        "is_safe_for_optimization": is_safe,
        "checks": checks,
        "rejection_reasons": rejection_reasons,
        "warnings": warnings,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
