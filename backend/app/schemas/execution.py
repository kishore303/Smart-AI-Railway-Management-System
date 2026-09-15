from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ResourceAvailabilityQuery(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime


class ResourceAllocateRequest(BaseModel):
    resource_id: int
    quantity: int = Field(default=1, ge=1, le=100)


class ExecutionStartRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class ExecutionCompleteRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class ExecutionCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ResourceOut(BaseModel):
    id: int
    resource_code: str
    name: Optional[str]
    department_code: str
    resource_type: Optional[str]
    quantity: int
    is_available: bool

    class Config:
        from_attributes = True


class AllocationOut(BaseModel):
    id: int
    block_id: int
    resource_id: int
    resource_code: str
    quantity_required: int
    allocated_from: datetime
    allocated_until: datetime
    status: str

    class Config:
        from_attributes = True


class ExecutionDetailResponse(BaseModel):
    optimized_block_id: int
    block_code: str
    status: str
    section_id: int
    track_id: Optional[int]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    department_code: str
    is_eligible_for_start: bool
    eligibility_reasons: List[str]
    safety_status: Optional[str]
    optimization_score: Optional[float]
    allocated_resources: List[AllocationOut]
    audit_history: List[dict]
