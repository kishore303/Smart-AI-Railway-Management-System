"""Emergency restriction safety rule."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest
from app.models.incident import Incident
from app.safety.rules.base import BaseSafetyRule, RuleResult


class EmergencyRestrictionRule(BaseSafetyRule):
    """Detects active, uncleared emergency incidents and restrictions in the section/track."""

    @property
    def rule_name(self) -> str:
        return "EMERGENCY_RESTRICTION"

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
                message="Emergency block designated for active corridor restoration.",
            )

        from sqlalchemy import or_
        q = db.query(Incident).filter(
            Incident.section_id == candidate.section_id,
            or_(Incident.response_status.is_(None), Incident.response_status.notin_(["CLEARED", "CLOSED"])),
            or_(Incident.status.is_(None), Incident.status.notin_(["INCIDENT_CLOSED", "CLOSED", "CLEARED", "RELEASED"])),
        )
        if blk:
            q = q.filter((Incident.block_request_id.is_(None)) | (Incident.block_request_id != blk.id))
        if candidate.track_id:
            q = q.filter((Incident.track_id == candidate.track_id) | (Incident.track_id.is_(None)))

        active_inc = q.first()
        if active_inc:
            return RuleResult(
                rule=self.rule_name,
                status="FAIL",
                severity="HARD",
                message=f"Emergency restriction: Active incident {active_inc.incident_code} ({active_inc.severity}) in section #{candidate.section_id}.",
                details={
                    "incident_code": active_inc.incident_code,
                    "severity": active_inc.severity,
                    "response_status": active_inc.response_status,
                },
            )

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No active emergency restrictions on the candidate corridor.",
        )
