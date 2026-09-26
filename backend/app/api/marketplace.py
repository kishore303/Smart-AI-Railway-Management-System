from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel

from app.database import get_db
from app.core.rbac import get_current_active_user
from app.models.user import User
from app.models.department import Department
from app.models.asset import Asset
from app.models.block import BlockRequest, BlockIntegrationRequest, OptimizedBlock, OptimizedBlockSource, BlockResourceAllocation
from app.models.maintenance import MaintenanceRequest
from app.models.railway import RailwaySection, Track
from app.models.resource import Resource
from app.models.audit import AuditLog
from app.models.notification import Notification

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


class JoinMarketplaceBlockRequest(BaseModel):
    target_block_id: int
    requesting_department_id: int
    maintenance_request_id: Optional[int] = None
    work_type: Optional[str] = "Routine Maintenance"
    remarks: Optional[str] = None
    estimated_duration_mins: Optional[int] = 60


@router.get("/blocks")
def list_marketplace_blocks(
    section_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns approved/scheduled blocks open for cross-department co-utilization and joint execution.
    """
    now = datetime.now(timezone.utc)
    
    # Query approved or active optimized blocks
    query = (
        db.query(OptimizedBlock)
        .filter(OptimizedBlock.end_time >= now - timedelta(hours=2))
        .order_by(OptimizedBlock.start_time.asc())
    )
    
    if status_filter:
        query = query.filter(OptimizedBlock.status == status_filter)
    
    blocks = query.limit(50).all()
    results = []
    
    for ob in blocks:
        # Get section & track info
        sec = db.query(RailwaySection).filter(RailwaySection.id == ob.section_id).first()
        trk = db.query(Track).filter(Track.id == ob.track_id).first() if ob.track_id else None
        
        # Get source requests to identify primary department
        sources = (
            db.query(OptimizedBlockSource)
            .filter(OptimizedBlockSource.optimized_block_id == ob.id)
            .all()
        )
        
        dept_ids = set()
        mreq_titles = []
        for src in sources:
            br = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
            if br:
                mr = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == br.maintenance_request_id).first()
                if mr:
                    dept_ids.add(mr.department_id)
                    mreq_titles.append(mr.maintenance_type or mr.description or f"Request #{mr.id}")
        
        # Primary department
        primary_dept = None
        if dept_ids:
            primary_dept = db.query(Department).filter(Department.id == list(dept_ids)[0]).first()
        
        if department_id and primary_dept and primary_dept.id != department_id:
            continue
        if section_id and ob.section_id != section_id:
            continue
        
        duration_mins = int((ob.end_time - ob.start_time).total_seconds() // 60) if ob.start_time and ob.end_time else 0
        
        # Check active integrations count
        join_count = len(sources)
        available_slots = max(0, 3 - join_count)
        
        results.append({
            "id": ob.id,
            "block_code": ob.block_code,
            "section_id": ob.section_id,
            "section_code": sec.section_code if sec else "N/A",
            "section_name": sec.name if sec else "N/A",
            "track_id": ob.track_id,
            "track_code": trk.track_code if trk else "ALL_TRACKS",
            "start_time": ob.start_time.isoformat() if ob.start_time else None,
            "end_time": ob.end_time.isoformat() if ob.end_time else None,
            "duration_mins": duration_mins,
            "status": ob.status,
            "primary_department_id": primary_dept.id if primary_dept else None,
            "primary_department_code": primary_dept.code if primary_dept else "UNKNOWN",
            "primary_department_name": primary_dept.name if primary_dept else "Unknown Dept",
            "participating_departments_count": join_count,
            "available_slots": available_slots,
            "co_utilization_open": available_slots > 0 and ob.status in ("APPROVED", "SCHEDULED"),
            "existing_works": mreq_titles,
            "optimization_score": float(ob.optimization_score) if ob.optimization_score else None,
        })
        
    return {
        "total": len(results),
        "marketplace_blocks": results,
    }


@router.post("/join")
def join_marketplace_block(
    payload: JoinMarketplaceBlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Submits a request for a department to join an existing marketplace block window.
    """
    ob = db.query(OptimizedBlock).filter(OptimizedBlock.id == payload.target_block_id).first()
    if not ob:
        raise HTTPException(status_code=404, detail="Target optimized block not found")
        
    req_dept = db.query(Department).filter(Department.id == payload.requesting_department_id).first()
    if not req_dept:
        raise HTTPException(status_code=404, detail="Requesting department not found")
        
    # Get primary block request for this optimized block
    src = db.query(OptimizedBlockSource).filter(OptimizedBlockSource.optimized_block_id == ob.id).first()
    if not src:
        raise HTTPException(status_code=400, detail="Target block has no linked block request")
        
    target_br = db.query(BlockRequest).filter(BlockRequest.id == src.block_request_id).first()
    target_mr = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == target_br.maintenance_request_id).first() if target_br else None
    
    target_dept_id = target_mr.department_id if target_mr else 1
    if target_dept_id == payload.requesting_department_id:
        raise HTTPException(status_code=400, detail="Cannot join a block already owned by your department")
        
    # Create or find a block request for the joining department
    source_br = None
    if payload.maintenance_request_id:
        source_br = db.query(BlockRequest).filter(BlockRequest.maintenance_request_id == payload.maintenance_request_id).first()
        
    if not source_br:
        # Get a sample asset for the section/track
        asset = db.query(Asset).filter(Asset.section_id == ob.section_id).first()
        asset_id = asset.id if asset else 1

        # Create a placeholder maintenance request & block request for this join request
        mreq = MaintenanceRequest(
            request_code=f"REQ-MKT-{int(datetime.now(timezone.utc).timestamp())}",
            asset_id=asset_id,
            description=payload.remarks or "Joined via Block Marketplace",
            department_id=payload.requesting_department_id,
            section_id=ob.section_id,
            track_id=ob.track_id,
            maintenance_type=payload.work_type or "ROUTINE",
            priority="MEDIUM",
            requested_start=ob.start_time,
            requested_end=ob.end_time,
            requested_duration_mins=payload.estimated_duration_mins or 60,
            status="APPROVED",
            requested_by=current_user.id,
        )
        db.add(mreq)
        db.flush()
        
        source_br = BlockRequest(
            block_code=f"BLK-MKT-{int(datetime.now(timezone.utc).timestamp())}",
            maintenance_request_id=mreq.id,
            section_id=ob.section_id,
            track_id=ob.track_id,
            requested_start=ob.start_time,
            requested_end=ob.end_time,
            block_type="JOINT",
            status="PENDING_APPROVAL",
        )
        db.add(source_br)
        db.flush()

    # Create BlockIntegrationRequest
    integration = BlockIntegrationRequest(
        source_block_id=source_br.id,
        target_block_id=target_br.id,
        requesting_department_id=payload.requesting_department_id,
        target_department_id=target_dept_id,
        section_id=ob.section_id,
        track_id=ob.track_id,
        overlap_start=ob.start_time,
        overlap_end=ob.end_time,
        overlap_duration_mins=payload.estimated_duration_mins,
        coordination_score=85.0,
        detection_reason=f"Joint execution requested via Marketplace by {req_dept.name}",
        spatial_status="SAME_SECTION",
        compatibility_status="COMPATIBLE",
        requested_by=current_user.id,
        final_status="PENDING",
    )
    db.add(integration)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="JOIN_MARKETPLACE_BLOCK",
        entity_type="block_integration_request",
        description=f"Joined block {ob.block_code} for dept {req_dept.name}",
    )
    db.add(audit)
    
    # Notification to target department
    notif = Notification(
        recipient_department_id=target_dept_id,
        type="BLOCK_INTEGRATION_OPPORTUNITY",
        title=f"Marketplace Join Request: {ob.block_code}",
        message=f"{req_dept.name} has requested to co-utilize block window {ob.block_code}.",
        priority="NORMAL",
    )
    db.add(notif)
    
    db.commit()
    db.refresh(integration)
    
    return {
        "success": True,
        "integration_request_id": integration.id,
        "message": f"Successfully submitted join request for block {ob.block_code}",
        "target_block_code": ob.block_code,
        "status": "PENDING",
    }


@router.get("/resources/timeline")
def get_resource_timeline(
    section_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns resource timeline & sharing availability across sections and time windows.
    """
    now = datetime.now(timezone.utc)
    
    res_query = db.query(Resource)
    if resource_type:
        res_query = res_query.filter(Resource.resource_type == resource_type)
    resources = res_query.limit(30).all()
    
    timeline_data = []
    
    for r in resources:
        # Get allocations
        allocs = (
            db.query(BlockResourceAllocation)
            .filter(BlockResourceAllocation.resource_id == r.id)
            .order_by(BlockResourceAllocation.allocated_from.asc())
            .all()
        )
        
        dept = db.query(Department).filter(Department.id == r.department_id).first() if r.department_id else None
        
        alloc_list = []
        for a in allocs:
            alloc_list.append({
                "allocation_id": a.id,
                "start": a.allocated_from.isoformat() if a.allocated_from else None,
                "end": a.allocated_until.isoformat() if a.allocated_until else None,
                "quantity": a.quantity_required,
                "status": a.status,
            })
            
        timeline_data.append({
            "resource_id": r.id,
            "resource_code": r.resource_code,
            "resource_name": r.name or r.resource_code,
            "resource_type": r.resource_type or "EQUIPMENT",
            "department_id": r.department_id,
            "department_name": dept.name if dept else "General",
            "quantity": r.quantity,
            "is_available": r.is_available,
            "available_from": r.available_from.isoformat() if r.available_from else None,
            "available_until": r.available_until.isoformat() if r.available_until else None,
            "allocations": alloc_list,
        })
        
    return {
        "timestamp": now.isoformat(),
        "resources_count": len(timeline_data),
        "timeline": timeline_data,
    }
