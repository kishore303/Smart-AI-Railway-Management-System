"""Stub for self-approval protection tests — not full maintenance module (Module 4)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.core.rbac import get_current_active_user, check_self_approval
from app.models.user import User

router = APIRouter(prefix="/api/maintenance", tags=["maintenance-stub"])


class VerifyRequest(BaseModel):
    requested_by: int


@router.post("/{request_id}/verify")
def verify_maintenance(request_id: int, payload: VerifyRequest, current_user: User = Depends(get_current_active_user)):
    # Self-approval protection: current_user.id != requested_by
    check_self_approval(current_user.id, payload.requested_by)
    return {"status": "verified", "request_id": request_id, "reviewed_by": current_user.id, "requested_by": payload.requested_by}
