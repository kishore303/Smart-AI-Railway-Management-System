"""Safety Rules Package."""
from app.safety.rules.base import BaseSafetyRule, RuleResult
from app.safety.rules.timing import TimingDurationRule
from app.safety.rules.track_conflict import TrackConflictRule
from app.safety.rules.section_conflict import SectionConflictRule
from app.safety.rules.existing_block import ExistingBlockRule
from app.safety.rules.train_conflict import TrainConflictRule
from app.safety.rules.adjacent_fouling import AdjacentFoulingRule
from app.safety.rules.resource_conflict import ResourceConflictRule
from app.safety.rules.maintenance_compatibility import MaintenanceCompatibilityRule
from app.safety.rules.protection import ProtectionRequirementRule
from app.safety.rules.operational import OperationalRestrictionRule
from app.safety.rules.emergency import EmergencyRestrictionRule

__all__ = [
    "BaseSafetyRule",
    "RuleResult",
    "TimingDurationRule",
    "TrackConflictRule",
    "SectionConflictRule",
    "ExistingBlockRule",
    "TrainConflictRule",
    "AdjacentFoulingRule",
    "ResourceConflictRule",
    "MaintenanceCompatibilityRule",
    "ProtectionRequirementRule",
    "OperationalRestrictionRule",
    "EmergencyRestrictionRule",
]
