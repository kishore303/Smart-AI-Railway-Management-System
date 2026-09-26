"""Existing block verification safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest, OptimizedBlock
from app.safety.rules.base import BaseSafetyRule, RuleResult


class ExistingBlockRule(BaseSafetyRule):
    """Verifies that the candidate does not collide with active/approved operational blocks."""

    @property
    def rule_name(self) -> str:
        return "EXISTING_BLOCK"

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
                message="Emergency block has preemptive possession over track/section operational blocks.",
            )

        # Check active blocks specifically (in APPROVED / ACTIVE status)
        active_blocks = db.query(BlockRequest).filter(
            BlockRequest.id != candidate.block_request_id,
            BlockRequest.section_id == candidate.section_id,
            BlockRequest.status.in_(["APPROVED", "ACTIVE"]),
            BlockRequest.requested_start < candidate.candidate_end,
            BlockRequest.requested_end > candidate.candidate_start,
        )
        if candidate.track_id:
            active_blocks = active_blocks.filter(
                (BlockRequest.track_id == candidate.track_id) | (BlockRequest.track_id.is_(None))
            )

        b = active_blocks.first()
        if b:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Collision with active/approved block {b.block_code} on section #{b.section_id}.",
                details={"colliding_block_code": b.block_code, "status": b.status},
            )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No collisions with active or approved blocks.",
        )
