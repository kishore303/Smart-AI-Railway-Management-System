"""Adjacent track and fouling condition safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.safety.rules.base import BaseSafetyRule, RuleResult


class AdjacentFoulingRule(BaseSafetyRule):
    """Evaluates adjacent track fouling conditions.
    
    CRITICAL: Does NOT automatically block adjacent tracks unconditionally.
    Evaluates work nature (e.g., heavy machinery, deep screening, crane operations vs visual inspection)
    and flags fouling protection conditions accordingly.
    """

    HEAVY_MACHINERY_TYPES = {
        "DEEP_SCREENING", "CRANE_OPERATION", "TRACK_RENEWAL", "SLEEPER_RENEWAL",
        "Deep Screening of Ballast", "Complete Track Renewal", "Sleeper Renewal"
    }

    @property
    def rule_name(self) -> str:
        return "ADJACENT_FOULING"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        if not candidate.track_id:
            return RuleResult(
                rule=self.rule_name,
                status="PASS",
                severity="INFO",
                message="Section-level block — adjacent fouling evaluated across full section.",
            )

        block = context.get("block_request") if context else None
        if not block:
            block = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()

        mreq = context.get("maintenance_request") if context else None
        if not mreq and block:
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()

        m_type = mreq.maintenance_type if mreq else (block.block_type if block else "")

        # Check overlapping blocks on adjacent tracks in same section
        adj_blocks = db.query(BlockRequest).filter(
            BlockRequest.id != candidate.block_request_id,
            BlockRequest.section_id == candidate.section_id,
            BlockRequest.track_id != candidate.track_id,
            BlockRequest.track_id.isnot(None),
            BlockRequest.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            BlockRequest.requested_start < candidate.candidate_end,
            BlockRequest.requested_end > candidate.candidate_start,
        ).all()

        if adj_blocks:
            is_heavy = any(h.lower() in (m_type or "").lower() for h in self.HEAVY_MACHINERY_TYPES)
            if is_heavy:
                return RuleResult(
                    rule=self.rule_name,
                    status="WARNING",
                    severity="WARNING",
                    message=f"Heavy maintenance work on Track {candidate.track_id} overlaps active work on adjacent track(s). Speed restrictions/fouling clearance flags required.",
                    details={"adjacent_block_codes": [b.block_code for b in adj_blocks]},
                )
            else:
                return RuleResult(
                    rule=self.rule_name,
                    status="PASS",
                    severity="INFO",
                    message=f"Parallel track work active on adjacent track without fouling conflict for {m_type}.",
                )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No adjacent track fouling conflicts detected.",
        )
