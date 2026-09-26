from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class IntegrationCreate(BaseModel):
    source_block_id: int
    target_block_id: int
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for integration request")


class IntegrationRespond(BaseModel):
    response: str = Field(description="ACCEPT | REJECT | MODIFY")
    reason: Optional[str] = Field(None, max_length=1000)
    modified_start: Optional[datetime] = None
    modified_end: Optional[datetime] = None


class IntegrationModify(BaseModel):
    modified_start: datetime
    modified_end: datetime
    reason: str = Field(min_length=3, max_length=1000, description="Reason for proposed modification")


class IntegrationOut(BaseModel):
    id: int
    source_block_id: int
    target_block_id: int
    source_block_code: Optional[str] = None
    target_block_code: Optional[str] = None
    requesting_department_id: int
    requesting_department_code: str
    target_department_id: int
    target_department_code: str
    section_id: Optional[int] = None
    track_id: Optional[int] = None
    overlap_start: Optional[datetime] = None
    overlap_end: Optional[datetime] = None
    overlap_duration_mins: Optional[int] = None
    coordination_score: Optional[float] = None
    detection_reason: Optional[str] = None
    spatial_status: Optional[str] = None
    compatibility_status: Optional[str] = None
    requested_by: int
    response_by: Optional[int] = None
    response: Optional[str] = None
    reason: Optional[str] = None
    modified_start: Optional[datetime] = None
    modified_end: Optional[datetime] = None
    final_status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    total: int
    items: List[IntegrationOut]
    skip: int
    limit: int


class JoinBlockRequest(BaseModel):
    block_id: int
    maintenance_request_id: int
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for requesting to join existing block")


class OpportunityDetectRequest(BaseModel):
    section_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class OpportunityDetectResponse(BaseModel):
    detected_count: int
    opportunities: List[IntegrationOut]


class IntegrationCancelResponse(BaseModel):
    message: str

