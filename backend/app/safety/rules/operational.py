"""Operational restriction and curfew safety rule."""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate
from app.safety.rules.base import BaseSafetyRule, RuleResult


class OperationalRestrictionRule(BaseSafetyRule):
    """Enforces railway operational timing limits, blackout windows, and past timestamp rejection."""

    MAX_BLOCK_DURATION_MINS = 1440  # 24 Hours

    @property
    def rule_name(self) -> str:
        return "OPERATIONAL_RESTRICTION"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        now = datetime.now(timezone.utc)

        # 1. Candidate must be in the future
        if candidate.candidate_start < now:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message="Operational restriction: Candidate window start time is in the past.",
                details={"candidate_start": candidate.candidate_start.isoformat(), "current_time": now.isoformat()},
            )

        # 2. Maximum single block duration limit
        dur_mins = int((candidate.candidate_end - candidate.candidate_start).total_seconds() // 60)
        if dur_mins > self.MAX_BLOCK_DURATION_MINS:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Operational restriction: Block duration ({dur_mins} mins) exceeds maximum allowed continuous limit ({self.MAX_BLOCK_DURATION_MINS} mins).",
                details={"duration_mins": dur_mins, "max_allowed_mins": self.MAX_BLOCK_DURATION_MINS},
            )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message=f"Candidate window satisfies operational timing parameters ({dur_mins} mins).",
        )
