"""Maintenance compatibility and cross-department co-location rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest, BlockIntegrationRequest
from app.models.maintenance import MaintenanceRequest
from app.safety.rules.base import BaseSafetyRule, RuleResult


class MaintenanceCompatibilityRule(BaseSafetyRule):
    """Evaluates cross-departmental maintenance co-location and compatibility."""

    @property
    def rule_name(self) -> str:
        return "MAINTENANCE_COMPATIBILITY"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        block = context.get("block_request") if context else None
        if not block:
            block = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()

        mreq = context.get("maintenance_request") if context else None
        if not mreq and block:
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()

        if not mreq:
            return RuleResult(
                rule=self.rule_name,
                status="PASS",
                severity="INFO",
                message="No maintenance request context — compatibility assumed valid.",
            )

        # Find overlapping block requests in the same section
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
                # Check whether formal Phase 4 cross-department integration was accepted
                integ = db.query(BlockIntegrationRequest).filter(
                    ((BlockIntegrationRequest.source_block_id == block.id) & (BlockIntegrationRequest.target_block_id == ob.id)) |
                    ((BlockIntegrationRequest.source_block_id == ob.id) & (BlockIntegrationRequest.target_block_id == block.id)),
                    BlockIntegrationRequest.final_status.in_(["ACCEPTED", "APPROVED"]),
                ).first()

                if not integ:
                    return RuleResult(
                        rule=self.rule_name,
                        status="FAIL",
                        severity="HARD",
                        message=f"Incompatible cross-department activity: Overlapping block {ob.block_code} (Dept #{omreq.department_id}) has no accepted coordination agreement.",
                        details={"conflicting_block_code": ob.block_code, "other_dept_id": omreq.department_id},
                    )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="Maintenance activity is compatible with corridor operations.",
        )
