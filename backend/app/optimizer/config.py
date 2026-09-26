from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class OptimizationWeights:
    train_delay_weight: float = 0.30
    affected_trains_weight: float = 0.20
    block_duration_weight: float = 0.10
    maintenance_priority_weight: float = 0.20
    cross_dept_coordination_weight: float = 0.15
    resource_utilization_weight: float = 0.05


def validate_weights(weights: OptimizationWeights) -> bool:
    total = (
        weights.train_delay_weight
        + weights.affected_trains_weight
        + weights.block_duration_weight
        + weights.maintenance_priority_weight
        + weights.cross_dept_coordination_weight
        + weights.resource_utilization_weight
    )
    if not (0.95 <= total <= 1.05):
        raise ValueError(f"Objective weights must sum to approximately 1.0 (got {total:.3f})")
    return True


@dataclass
class OptimizationConfig:
    version: str = "v1.0"
    scale_factor: int = 1000
    solver_time_limit_seconds: float = 10.0
    solver_workers: int = 8
    solver_random_seed: int = 42
    weights: OptimizationWeights = field(default_factory=OptimizationWeights)
