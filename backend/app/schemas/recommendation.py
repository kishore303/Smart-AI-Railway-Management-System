from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class RecommendationRequestSummary(BaseModel):
    maintenance_request_id: Optional[int]
    request_code: Optional[str]
    department_code: Optional[str]
    asset_id: Optional[int]
    asset_code: Optional[str]
    section_id: Optional[int]
    section_code: Optional[str]
    track_id: Optional[int]
    track_code: Optional[str]
    maintenance_type: Optional[str]
    priority: Optional[str]
    requested_start: Optional[datetime]
    requested_end: Optional[datetime]
    requested_duration_mins: Optional[int]


class SafetySummary(BaseModel):
    candidate_id: Optional[int]
    overall_status: Optional[str]
    is_safe_for_optimization: Optional[bool]
    checks: Optional[List[Dict[str, Any]]]
    rejection_reasons: Optional[List[str]]
    warnings: Optional[List[str]]
    validated_at: Optional[datetime]
    validated_by: Optional[int]
    planning_safety_status: Optional[str]


class OptimizationSummary(BaseModel):
    optimization_score: Optional[float]
    objective_value: Optional[float]
    objective_summary: Optional[Dict[str, Any]]
    explanation: Optional[str]
    solver_status: Optional[str]
    total_considered: Optional[int]
    eligible: Optional[int]


class AlternativeCandidate(BaseModel):
    candidate_id: int
    candidate_start: Optional[datetime]
    candidate_end: Optional[datetime]
    duration_mins: Optional[int]
    safety_status: Optional[str]
    safety_overall: Optional[str]
    is_safe: Optional[bool]
    optimization_eligible: bool
    predicted_delay: Optional[int]
    asset_risk: Optional[float]
    reason_not_selected: str


class IntegrationSummary(BaseModel):
    integration_id: Optional[int]
    source_block: Optional[str]
    target_block: Optional[str]
    requesting_dept: Optional[str]
    target_dept: Optional[str]
    compatibility_status: Optional[str]
    overlap_mins: Optional[int]
    final_status: Optional[str]


class RecommendationResponse(BaseModel):
    optimized_block_id: int
    block_code: str
    status: str
    is_eligible_for_approval: bool
    eligibility_reasons: List[str]
    request_summary: RecommendationRequestSummary
    safety_summary: SafetySummary
    optimization_summary: OptimizationSummary
    selected_recommendation: Dict[str, Any]
    alternatives: List[AlternativeCandidate]
    integration_summary: List[IntegrationSummary]
    warnings: List[str]
    decision_status: str
    decision_history: List[Dict[str, Any]]


class OfficialDecisionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000, description="Reason/comments for decision")
    new_start_time: Optional[datetime] = None
    new_end_time: Optional[datetime] = None
    new_candidate_id: Optional[int] = None


class OfficialDecisionResponse(BaseModel):
    optimized_block_id: int
    new_status: str
    decision: str
    reason: Optional[str]
    decided_by: int
    decided_at: datetime
    requires_revalidation: bool
    requires_reoptimization: bool
