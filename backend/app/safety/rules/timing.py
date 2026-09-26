"""Timing and duration safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.safety.rules.base import BaseSafetyRule, RuleResult


class TimingDurationRule(BaseSafetyRule):
    """Verifies that the candidate window is chronologically valid and satisfies duration bounds."""

    @property
    def rule_name(self) -> str:
        return "TIMING"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        if candidate.candidate_start >= candidate.candidate_end:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message="Candidate start timestamp must precede candidate end timestamp.",
            )

        duration_mins = int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60)
        if duration_mins <= 0:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Candidate duration is invalid ({duration_mins} mins).",
            )

        block = context.get("block_request") if context else None
        if not block:
            block = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()

        mreq = context.get("maintenance_request") if context else None
        if not mreq and block:
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()

        # Check required work duration
        required_duration = None
        if candidate.predicted_duration_mins:
            required_duration = candidate.predicted_duration_mins
        elif mreq and mreq.requested_duration_mins:
            required_duration = mreq.requested_duration_mins

        if required_duration and duration_mins < required_duration:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Candidate duration ({duration_mins} mins) is shorter than required work duration ({required_duration} mins).",
                details={"candidate_duration_mins": duration_mins, "required_duration_mins": required_duration},
            )

        # Check within requested availability window if block_request is available
        if block and block.requested_start and block.requested_end:
            # Candidate should not exceed allowed window bounds by more than configured grace period
            pass

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message=f"Candidate time window is valid ({duration_mins} mins).",
            details={"duration_mins": duration_mins, "required_duration_mins": required_duration},
        )
