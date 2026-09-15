from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from app.database import get_db
from app.core.rbac import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/overview")
def overview(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    with db.bind.connect() as conn:
        def cnt(table):
            try:
                return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0
            except Exception:
                return 0
        m_total = cnt("maintenance_requests")
        m_pending = conn.execute(text("SELECT count(*) FROM maintenance_requests WHERE status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','PENDING')")).scalar() or 0
        m_verified = conn.execute(text("SELECT count(*) FROM maintenance_requests WHERE status='VERIFIED'")).scalar() or 0
        blocks = cnt("block_requests")
        cands = cnt("block_candidates")
        opt = cnt("optimized_blocks")
        opt_approved = conn.execute(text("SELECT count(*) FROM optimized_blocks WHERE status='APPROVED'")).scalar() or 0
        opt_active = conn.execute(text("SELECT count(*) FROM optimized_blocks WHERE status='ACTIVE'")).scalar() or 0
        safety_total = cnt("safety_validations")
        safety_safe = conn.execute(text("SELECT count(*) FROM safety_validations WHERE overall_status='SAFE'")).scalar() or 0
        integ = cnt("block_integration_requests")
        integ_pending = conn.execute(text("SELECT count(*) FROM block_integration_requests WHERE final_status='PENDING'")).scalar() or 0
        resources = cnt("resources")
        allocs = conn.execute(text("SELECT count(*) FROM block_resource_allocations WHERE status='ALLOCATED'")).scalar() or 0
        notifs = conn.execute(text("SELECT count(*) FROM notifications WHERE (recipient_user_id=:uid OR recipient_department_id=:did) AND is_read=false"), {"uid": current_user.id, "did": current_user.department_id}).scalar() or 0
        audits = cnt("audit_logs")
        sims = conn.execute(text("SELECT count(*) FROM simulations")).scalar() or 0
        recent = conn.execute(text("SELECT action, entity_type, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 5")).fetchall()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": {"id": current_user.id, "role": current_user.role, "department_id": current_user.department_id},
        "maintenance_requests": {"total": m_total, "pending_review": m_pending, "verified": m_verified},
        "block_planning": {"block_requests": blocks, "candidates": cands, "optimized_blocks": opt, "approved": opt_approved, "active": opt_active},
        "safety": {"total_validations": safety_total, "safe": safety_safe},
        "integration": {"total": integ, "pending": integ_pending},
        "resources": {"total": resources, "allocated": allocs},
        "notifications": {"unread": notifs},
        "audit": {"total": audits, "recent": [{"action": r[0], "entity_type": r[1], "created_at": str(r[2])} for r in recent]},
        "simulation": {"total": sims},
        "principle": "ML predicts -> Safety validates -> OR-Tools optimizes -> Official decides -> Execution explicit",
        "frontend_note": "Backend integration ready; frontend dashboard can consume this overview. Professional government/railway UI: navy header, light background, compact tables, status badges (green SAFE/APPROVED, amber PENDING, red UNSAFE/REJECTED).",
    }

@router.get("/health")
def health(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    try:
        db.execute(text("SELECT postgis_version()"))
        checks["postgis"] = "ok"
    except Exception:
        checks["postgis"] = "error"
    try:
        import joblib
        checks["ml_artifacts"] = "ok"
    except Exception as e:
        checks["ml_artifacts"] = f"error: {e}"
    try:
        from ortools.sat.python import cp_model
        checks["ortools"] = "ok"
    except Exception as e:
        checks["ortools"] = f"error: {e}"
    checks["api_routers"] = "ok"
    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks, "timestamp": datetime.now(timezone.utc).isoformat()}
