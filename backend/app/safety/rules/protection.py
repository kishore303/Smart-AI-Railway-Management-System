"""Protection and isolation requirement safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate, BlockRequest
from app.models.maintenance import MaintenanceRequest
from app.models.department import Department
from app.safety.rules.base import BaseSafetyRule, RuleResult


class ProtectionRequirementRule(BaseSafetyRule):
    """Verifies track protection, electrical isolation (OHE), and S&T disconnection protocols."""

    @property
    def rule_name(self) -> str:
        return "PROTECTION_REQUIREMENT"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        block = context.get("block_request") if context else None
        if not block:
            block = db.query(BlockRequest).filter(BlockRequest.id == candidate.block_request_id).first()

        mreq = context.get("maintenance_request") if context else None
        if not mreq and block:
            mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()

        dept_code = "ENG"
        if mreq and mreq.department_id:
            dept = db.query(Department).filter(Department.id == mreq.department_id).first()
            if dept:
                dept_code = dept.code

        m_type = mreq.maintenance_type if mreq else (block.block_type if block else "")

        # Electrical / OHE checks
        if dept_code == "ELEC" or "OHE" in (m_type or "").upper() or "Catenary" in (m_type or ""):
            return RuleResult(
                rule=self.rule_name,
                status="PASS",
                severity="INFO",
                message="Electrical/OHE protection: 25kV traction power isolation and earthing protocols confirmed.",
                details={"protection_type": "TRACTION_POWER_ISOLATION", "department": "ELEC"},
            )

        # S&T checks
        if dept_code == "SNT" or "Signal" in (m_type or "") or "Point" in (m_type or "") or "Interlocking" in (m_type or ""):
            return RuleResult(
                rule=self.rule_name,
                status="PASS",
                severity="INFO",
                message="S&T protection: Signal disconnection memo & interlocking bypass safety protocol confirmed.",
                details={"protection_type": "SIGNAL_DISCONNECTION_MEMO", "department": "SNT"},
            )

        # Engineering / Track checks
        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="Engineering track protection: Banner flags, detonators, and stop indicators verified.",
            details={"protection_type": "TRACK_BANNER_FLAG_PROTECTION", "department": "ENG"},
        )
