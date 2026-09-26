"""Resource conflict safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, OptimizedBlock, BlockResourceAllocation, OptimizedBlockSource
from app.models.resource import Resource
from app.safety.rules.base import BaseSafetyRule, RuleResult


class ResourceConflictRule(BaseSafetyRule):
    """Detects resource allocation conflicts (crews, machinery, heavy equipment)."""

    @property
    def rule_name(self) -> str:
        return "RESOURCE_CONFLICT"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        # Exclude optimized blocks linked to this block request
        linked_obs = db.query(OptimizedBlockSource.optimized_block_id).filter(
            OptimizedBlockSource.block_request_id == candidate.block_request_id
        ).all()
        linked_ids = [r[0] for r in linked_obs]

        # Check overlapping optimized blocks that hold active resource allocations
        q_overlapping = db.query(OptimizedBlock).filter(
            OptimizedBlock.section_id == candidate.section_id,
            OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            OptimizedBlock.start_time < candidate.candidate_end,
            OptimizedBlock.end_time > candidate.candidate_start,
        )
        if linked_ids:
            q_overlapping = q_overlapping.filter(OptimizedBlock.id.notin_(linked_ids))

        overlapping_obs = q_overlapping.all()
        for ob in overlapping_obs:
            alloc = db.query(BlockResourceAllocation).filter(
                BlockResourceAllocation.block_id == ob.id,
                BlockResourceAllocation.allocated_from < candidate.candidate_end,
                BlockResourceAllocation.allocated_until > candidate.candidate_start,
                BlockResourceAllocation.status == "ALLOCATED",
            ).first()
            if alloc:
                res_rec = db.query(Resource).filter(Resource.id == alloc.resource_id).first()
                res_name = res_rec.name if res_rec else f"Resource #{alloc.resource_id}"
                return RuleResult(
                    rule=self.rule_name,
                    status="FAIL",
                    severity="HARD",
                    message=f"Resource conflict: {res_name} is already allocated to overlapping block {ob.block_code}.",
                    details={
                        "conflicting_block_code": ob.block_code,
                        "resource_id": alloc.resource_id,
                        "resource_name": res_name,
                    },
                )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="Required railway resources and machinery are available.",
        )
