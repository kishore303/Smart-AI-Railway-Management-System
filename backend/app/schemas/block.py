from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BlockRequestCreate(BaseModel):
    maintenance_request_id: int
    requested_start: datetime
    requested_end: datetime
    block_type: Optional[str] = Field(None, max_length=50, description="e.g. TRAFFIC, POWER, SIGNAL")


class BlockRequestOut(BaseModel):
    id: int
    block_code: str
    maintenance_request_id: int
    section_id: int
    track_id: Optional[int]
    requested_start: datetime
    requested_end: datetime
    duration_mins: Optional[int]
    block_type: Optional[str]
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class BlockRequestListResponse(BaseModel):
    total: int
    items: List[BlockRequestOut]
    skip: int
    limit: int


class CandidateCreate(BaseModel):
    # For manual candidate creation, but generate will auto-create
    candidate_start: datetime
    candidate_end: datetime
    predicted_duration_mins: Optional[int] = None


class CandidateOut(BaseModel):
    id: int
    block_request_id: int
    section_id: int
    track_id: Optional[int]
    candidate_start: datetime
    candidate_end: datetime
    predicted_duration_mins: Optional[int]
    predicted_delay_mins: Optional[int]
    asset_risk_score: Optional[float]
    safety_status: str
    safety_rejection_reason: Optional[str]
    optimization_score: Optional[float]
    is_selected: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class CandidateGenerateResponse(BaseModel):
    generated: int
    candidates: List[CandidateOut]
    message: str
