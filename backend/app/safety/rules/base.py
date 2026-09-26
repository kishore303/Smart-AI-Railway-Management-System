"""Base interface and result models for Safety Engine rules."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate


@dataclass
class RuleResult:
    rule: str
    status: str  # "PASS" | "WARNING" | "FAIL"
    severity: str  # "INFO" | "WARNING" | "HARD"
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "check": self.rule,
            "rule": self.rule,
            "status": self.status,
            "severity": self.severity,
            "reason": self.message,
            "message": self.message,
        }
        if self.status == "WARNING":
            d["warning"] = self.message
        if self.details:
            d["details"] = self.details
        return d


class BaseSafetyRule(ABC):
    """Abstract base class for all deterministic railway safety rules."""

    @property
    @abstractmethod
    def rule_name(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        """Evaluate the rule against the candidate and return structured RuleResult."""
        pass
