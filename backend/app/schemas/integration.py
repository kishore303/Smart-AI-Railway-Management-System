from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class IntegrationCreate(BaseModel):
    source_block_id: int
    target_block_id: int
    reason: Optional[str] = Field(None, max_length=1000, description="Reason for integration request")


class IntegrationOut(BaseModel):
    id: int
    source_block_id: int
    target_block_id: int
    requesting_department_id: int
    requesting_department_code: str
    target_department_id: int
    target_department_code: str
    overlap_duration_mins: Optional[int]
    compatibility_status: Optional[str]
    requested_by: int
    response_by: Optional[int]
    response: Optional[str]
    reason: Optional[str]
    final_status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    total: int
    items: List[IntegrationOut]
    skip: int
    limit: int


class IntegrationRespond(BaseModel):
    response: str = Field(description="ACCEPT | REJECT | MODIFY")
    reason: Optional[str] = Field(None, max_length=1000)


class IntegrationCancelResponse(BaseModel):
    message: str
