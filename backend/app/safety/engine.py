"""Deterministic Railway Safety Validation Engine.

Strict Architectural Principle:
AI Predicts -> Rules Validate -> OR-Tools Optimizes -> Railway Official Decides.

Evaluates block candidates across all deterministic safety dimensions:
- Timing and duration adequacy
- Track-level block conflicts
- Section-level corridor closures
- Existing active and scheduled blocks
- Timetable train traffic and movement conflicts
- Adjacent track fouling and machinery clearance
- Resource and machinery contention
- Cross-department maintenance compatibility (integrating Phase 4 accepted coordination)
- Electrical / OHE traction power isolation and S&T disconnection protection
- Operational limits and curfew compliance
- Emergency incident restrictions
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.models.safety import SafetyValidation
from app.models.audit import AuditLog
from app.safety.rules import (
    BaseSafetyRule,
    TimingDurationRule,
    TrackConflictRule,
    SectionConflictRule,
    ExistingBlockRule,
    TrainConflictRule,
    AdjacentFoulingRule,
    ResourceConflictRule,
    MaintenanceCompatibilityRule,
    ProtectionRequirementRule,
    OperationalRestrictionRule,
    EmergencyRestrictionRule,
)


class SafetyEngine:
    """Modular Safety Engine executing deterministic railway rule validations."""

    def __init__(self):
        self.rules: List[BaseSafetyRule] = [
            TimingDurationRule(),
            TrackConflictRule(),
            SectionConflictRule(),
            ExistingBlockRule(),
            TrainConflictRule(),
            AdjacentFoulingRule(),
            ResourceConflictRule(),
            MaintenanceCompatibilityRule(),
            ProtectionRequirementRule(),
            OperationalRestrictionRule(),
            EmergencyRestrictionRule(),
        ]

    def evaluate_candidate(
        self,
        candidate: BlockCandidate,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute all modular rules against the candidate and determine overall safety status."""
        checks: List[Dict[str, Any]] = []
        rejection_reasons: List[str] = []
        warnings: List[str] = []

        ctx = context or {}
        if "block_request" not in ctx:
            ctx["block_request"] = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()
        if "maintenance_request" not in ctx and ctx.get("block_request"):
            ctx["maintenance_request"] = db.query(MaintenanceRequest).filter(
                MaintenanceRequest.id == ctx["block_request"].maintenance_request_id
            ).first()

        for rule in self.rules:
            try:
                res = rule.evaluate(candidate, db, context=ctx)
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                res = rule.evaluate(candidate, db, context=ctx) if False else None
                from app.safety.rules.base import RuleResult
                res = RuleResult(
                    rule=rule.rule_name,
                    status="FAIL",
                    severity="HARD",
                    message=f"Rule evaluation encountered error: {str(e)}",
                )

            res_dict = res.to_dict()
            checks.append(res_dict)

            if res.status == "FAIL" and res.severity == "HARD":
                rejection_reasons.append(f"{res.rule}: {res.message}")
            if res.status == "WARNING":
                warnings.append(f"{res.rule}: {res.message}")

        # Overall Status: SAFE only if no HARD failures
        has_hard_fail = len(rejection_reasons) > 0
        overall_status = "UNSAFE" if has_hard_fail else "SAFE"
        is_safe = not has_hard_fail

        return {
            "candidate_id": candidate.id,
            "block_request_id": candidate.block_request_id,
            "overall_status": overall_status,
            "is_safe_for_optimization": is_safe,
            "checks": checks,
            "rejection_reasons": rejection_reasons,
            "warnings": warnings,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Deterministic Safety Engine validation only. Indicates feasibility for OR-Tools optimization. Does not authorize final block execution.",
        }


# Singleton engine instance
safety_engine = SafetyEngine()


def validate_candidate(
    candidate: BlockCandidate,
    db: Session,
    user_id: Optional[int] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Validate a candidate, optionally persisting SafetyValidation to database."""
    result = safety_engine.evaluate_candidate(candidate, db)

    # Sync planning safety_status on the candidate itself (FEASIBLE / INFEASIBLE or SAFE / UNSAFE)
    candidate_safety_status = "FEASIBLE" if result["is_safe_for_optimization"] else "INFEASIBLE"
    candidate.safety_status = candidate_safety_status
    candidate.safety_rejection_reason = "; ".join(result["rejection_reasons"]) if result["rejection_reasons"] else None

    if persist:
        existing = db.query(SafetyValidation).filter(SafetyValidation.candidate_id == candidate.id).first()
        if existing:
            existing.overall_status = result["overall_status"]
            existing.is_safe_for_optimization = result["is_safe_for_optimization"]
            existing.checks = result["checks"]
            existing.rejection_reasons = result["rejection_reasons"]
            existing.warnings = result["warnings"]
            if user_id:
                existing.validated_by = user_id
            existing.validated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            sv_id = existing.id
        else:
            sv = SafetyValidation(
                candidate_id=candidate.id,
                block_request_id=candidate.block_request_id,
                overall_status=result["overall_status"],
                is_safe_for_optimization=result["is_safe_for_optimization"],
                checks=result["checks"],
                rejection_reasons=result["rejection_reasons"],
                warnings=result["warnings"],
                validated_by=user_id,
                validated_at=datetime.now(timezone.utc),
            )
            db.add(sv)
            db.commit()
            db.refresh(sv)
            sv_id = sv.id

        db.commit()

        # Audit log
        if user_id:
            audit = AuditLog(
                user_id=user_id,
                action="SAFETY_VALIDATION",
                entity_type="SafetyValidation",
                entity_id=sv_id,
                description=f"Safety validation for candidate #{candidate.id}: {result['overall_status']} (is_safe={result['is_safe_for_optimization']})",
            )
            db.add(audit)
            db.commit()

    return result


def revalidate_candidate(candidate_id: int, db: Session, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Re-evaluate an existing candidate against live operational state and update persistence."""
    candidate = db.query(BlockCandidate).filter(BlockCandidate.id == candidate_id).first()
    if not candidate:
        raise ValueError(f"Block candidate #{candidate_id} not found")

    result = validate_candidate(candidate, db, user_id=user_id, persist=True)

    if user_id:
        audit = AuditLog(
            user_id=user_id,
            action="CANDIDATE_REVALIDATED",
            entity_type="BlockCandidate",
            entity_id=candidate.id,
            description=f"Revalidated candidate #{candidate.id}: status={result['overall_status']}",
        )
        db.add(audit)
        db.commit()

    return result


def get_safe_candidates(block_request_id: int, db: Session) -> List[Dict[str, Any]]:
    """Retrieve only SAFE candidates (is_safe_for_optimization=True) for a block request to pass to Phase 7."""
    validations = (
        db.query(SafetyValidation, BlockCandidate)
        .join(BlockCandidate, SafetyValidation.candidate_id == BlockCandidate.id)
        .filter(
            SafetyValidation.block_request_id == block_request_id,
            SafetyValidation.is_safe_for_optimization.is_(True),
        )
        .all()
    )

    safe_list = []
    for sv, cand in validations:
        duration_mins = int((cand.candidate_end - cand.candidate_start).total_seconds() // 60)
        safe_list.append({
            "candidate_id": cand.id,
            "block_request_id": cand.block_request_id,
            "section_id": cand.section_id,
            "track_id": cand.track_id,
            "start_time": cand.candidate_start.isoformat(),
            "end_time": cand.candidate_end.isoformat(),
            "duration_minutes": duration_mins,
            "predicted_duration_mins": cand.predicted_duration_mins,
            "predicted_delay_mins": cand.predicted_delay_mins,
            "affected_train_count": cand.affected_train_count,
            "asset_risk_score": float(cand.asset_risk_score) if cand.asset_risk_score is not None else None,
            "safety_status": sv.overall_status,
            "is_safe_for_optimization": sv.is_safe_for_optimization,
            "warnings": sv.warnings or [],
            "validated_at": sv.validated_at.isoformat() if sv.validated_at else None,
        })

    return safe_list
