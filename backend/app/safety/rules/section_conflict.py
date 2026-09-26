"""Section-level conflict safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest, OptimizedBlock, OptimizedBlockSource
from app.safety.rules.base import BaseSafetyRule, RuleResult


class SectionConflictRule(BaseSafetyRule):
    """Evaluates section-wide blanket closures (where track_id is NULL or whole corridor shutdown)."""

    @property
    def rule_name(self) -> str:
        return "SECTION_CONFLICT"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        ctx = context or {}
        blk = ctx.get("block_request")
        if not blk and candidate.block_request_id:
            blk = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()
        is_emergency = bool(blk and blk.block_code and blk.block_code.startswith("EMG-"))
        if is_emergency:
            return RuleResult(
                rule=self.rule_name,
                status="PASS",
                severity="INFO",
                message="Emergency block has preemptive possession over section conflicts.",
            )
        active_statuses = ["APPROVED", "ACTIVE", "PROPOSED", "PENDING_APPROVAL", "UNDER_REVIEW"]
        q = db.query(BlockRequest).filter(
            BlockRequest.id != candidate.block_request_id,
            BlockRequest.section_id == candidate.section_id,
            BlockRequest.track_id.is_(None),
            BlockRequest.status.in_(active_statuses),
            BlockRequest.requested_start < candidate.candidate_end,
            BlockRequest.requested_end > candidate.candidate_start,
        )
        conflicting_section_block = q.first()
        if conflicting_section_block:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Section conflict: Section #{candidate.section_id} has an active corridor-wide block {conflicting_section_block.block_code}.",
                details={"conflicting_block_code": conflicting_section_block.block_code},
            )

        # Check section-level optimized block
        linked_obs = db.query(OptimizedBlockSource.optimized_block_id).filter(
            OptimizedBlockSource.block_request_id == candidate.block_request_id
        ).all()
        linked_ids = [r[0] for r in linked_obs]

        q_opt = db.query(OptimizedBlock).filter(
            OptimizedBlock.section_id == candidate.section_id,
            OptimizedBlock.track_id.is_(None),
            OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            OptimizedBlock.start_time < candidate.candidate_end,
            OptimizedBlock.end_time > candidate.candidate_start,
        )
        if linked_ids:
            q_opt = q_opt.filter(OptimizedBlock.id.notin_(linked_ids))

        conflicting_opt_section = q_opt.first()
        if conflicting_opt_section:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Section conflict: Section #{candidate.section_id} has a whole-corridor optimized block {conflicting_opt_section.block_code}.",
            )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No section-level corridor shutdown detected.",
        )
