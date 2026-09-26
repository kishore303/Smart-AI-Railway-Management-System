from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MaintenanceCreate(BaseModel):
    asset_id: int
    section_id: int
    track_id: Optional[int] = None
    maintenance_type: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    priority: str = Field(default="MEDIUM", description="LOW/MEDIUM/HIGH/CRITICAL")
    requested_start: datetime
    requested_end: datetime
    resource_ids: Optional[List[int]] = Field(None, description="optional resource IDs to validate")
    # Note: department derived from asset or current_user, but allow override for admin? For now derive from current_user dept or asset dept

    class Config:
        json_schema_extra = {
            "example": {
                "asset_id": 1,
                "section_id": 1,
                "track_id": 1,
                "maintenance_type": "Track Tamping",
                "priority": "HIGH",
                "requested_start": "2026-09-20T22:00:00Z",
                "requested_end": "2026-09-20T23:30:00Z",
                "description": "SYN test maintenance",
            }
        }


class MaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    priority: Optional[str] = None
    requested_start: Optional[datetime] = None
    requested_end: Optional[datetime] = None
    track_id: Optional[int] = None
    resource_ids: Optional[List[int]] = None


class MaintenanceOut(BaseModel):
    id: int
    request_code: str
    asset_id: int
    department_id: int
    department_code: str
    requested_by: int
    section_id: int
    track_id: Optional[int]
    maintenance_type: str
    description: Optional[str]
    priority: str
    requested_start: datetime
    requested_end: datetime
    requested_duration_mins: Optional[int]
    status: str
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    revision_notes: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class MaintenanceListResponse(BaseModel):
    total: int
    items: List[MaintenanceOut]
    skip: int
    limit: int


class StatusTransition(BaseModel):
    new_status: str = Field(description="Target status, e.g. SUBMITTED, UNDER_REVIEW, VERIFIED, REVISION_REQUIRED, REJECTED, BLOCK_PLANNING, etc.")
    reason: Optional[str] = Field(None, max_length=1000, description="rejection_reason or revision_notes depending on target")


# Module 5 — Review & Verification dedicated schemas
class ReviewAction(BaseModel):
    action: str = Field(description="VERIFY | REJECT | REVISION_REQUIRED")
    reason: Optional[str] = Field(None, max_length=1000, description="rejection_reason for REJECT or revision_notes for REVISION_REQUIRED")
    revision_notes: Optional[str] = Field(None, max_length=1000)
    rejection_reason: Optional[str] = Field(None, max_length=1000)


class ReasonPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=1000, description="Mandatory reason for rejection or revision request")


class SubmitPayload(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000, description="Optional submission notes")


class ReviewHistoryItem(BaseModel):
    id: int
    action: str
    user_id: Optional[int]
    user_name: Optional[str]
    user_role: Optional[str]
    old_status: Optional[str]
    new_status: Optional[str]
    description: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReviewQueueResponse(BaseModel):
    total: int
    items: List[MaintenanceOut]
    skip: int
    limit: int


class MaintenanceAreaCreate(BaseModel):
    section_id: int
    track_id: int
    start_km: float = Field(..., gt=0, description="Start KM must be positive")
    end_km: float = Field(..., gt=0, description="End KM must be positive")


class MaintenanceAreaUpdate(BaseModel):
    start_km: Optional[float] = Field(None, gt=0, description="Start KM must be positive")
    end_km: Optional[float] = Field(None, gt=0, description="End KM must be positive")


class MaintenanceAreaOut(BaseModel):
    id: int
    maintenance_request_id: int
    section_id: int
    track_id: int
    start_km: float
    end_km: float
    length_km: float
    defined_by: int
    defined_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

