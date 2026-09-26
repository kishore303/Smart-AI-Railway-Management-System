"""Track conflict safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest, OptimizedBlock, OptimizedBlockSource
from app.safety.rules.base import BaseSafetyRule, RuleResult


class TrackConflictRule(BaseSafetyRule):
    """Detects overlapping blocks on the same track within the section."""

    @property
    def rule_name(self) -> str:
        return "TRACK_CONFLICT"

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
                message="Emergency block has preemptive possession over track conflicts.",
            )
        active_statuses = ["APPROVED", "ACTIVE", "PROPOSED", "PENDING_APPROVAL", "UNDER_REVIEW"]
        q_br = db.query(BlockRequest).filter(
            BlockRequest.id != candidate.block_request_id,
            BlockRequest.section_id == candidate.section_id,
            BlockRequest.status.in_(active_statuses),
            BlockRequest.requested_start < candidate.candidate_end,
            BlockRequest.requested_end > candidate.candidate_start,
        )
        if candidate.track_id:
            q_br = q_br.filter((BlockRequest.track_id == candidate.track_id) | (BlockRequest.track_id.is_(None)))

        conflicting_br = q_br.first()
        if conflicting_br:
            track_desc = f"Track {candidate.track_id}" if candidate.track_id else "Section track"
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Track conflict: {track_desc} overlaps existing block request {conflicting_br.block_code} ({conflicting_br.status}).",
                details={
                    "conflicting_block_code": conflicting_br.block_code,
                    "conflicting_block_id": conflicting_br.id,
                    "section_id": candidate.section_id,
                    "track_id": candidate.track_id,
                },
            )

        # 2. Overlapping Optimized Blocks (excluding blocks linked to this block request to avoid false self-conflict)
        linked_obs = db.query(OptimizedBlockSource.optimized_block_id).filter(
            OptimizedBlockSource.block_request_id == candidate.block_request_id
        ).all()
        linked_ids = [r[0] for r in linked_obs]

        q_ob = db.query(OptimizedBlock).filter(
            OptimizedBlock.section_id == candidate.section_id,
            OptimizedBlock.status.notin_(["REJECTED", "CANCELLED", "COMPLETED"]),
            OptimizedBlock.start_time < candidate.candidate_end,
            OptimizedBlock.end_time > candidate.candidate_start,
        )
        if candidate.track_id:
            q_ob = q_ob.filter((OptimizedBlock.track_id == candidate.track_id) | (OptimizedBlock.track_id.is_(None)))
        if linked_ids:
            q_ob = q_ob.filter(OptimizedBlock.id.notin_(linked_ids))

        conflicting_ob = q_ob.first()
        if conflicting_ob:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Track conflict: Overlaps active/scheduled optimized block {conflicting_ob.block_code}.",
                details={
                    "conflicting_optimized_block_code": conflicting_ob.block_code,
                    "conflicting_optimized_block_id": conflicting_ob.id,
                },
            )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No track-level block conflicts detected on the selected track.",
        )
