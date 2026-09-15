from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.database import get_db
from app.core.rbac import get_current_active_user
from app.core.security import decode_token
from app.core.websocket_manager import manager
from app.models.user import User
from app.models.notification import Notification
from app.models.department import Department

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("")
def list_notifications(
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # Dept-scoped: user sees own + dept notifications where they are member
    # Admin sees all? For now, same as before: user sees own user_id OR dept
    q = db.query(Notification).filter(
        (Notification.recipient_user_id == current_user.id) | (Notification.recipient_department_id == current_user.department_id)
    )
    if unread_only:
        q = q.filter(Notification.is_read == False)
    total = q.count()
    items = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "priority": n.priority,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            } for n in items
        ],
        "skip": skip,
        "limit": limit,
    }

@router.get("/unread/count")
def unread_count(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    cnt = db.query(Notification).filter(
        ((Notification.recipient_user_id == current_user.id) | (Notification.recipient_department_id == current_user.department_id)),
        Notification.is_read == False,
    ).count()
    return {"unread": cnt}

@router.post("/{notification_id}/read")
def mark_read(notification_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    # Check ownership: must be for this user or their dept
    if n.recipient_user_id and n.recipient_user_id != current_user.id:
        # If it's user-specific and not for this user, check if admin
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=403, detail="Not your notification")
    if n.recipient_department_id and n.recipient_department_id != current_user.department_id:
        if current_user.role not in ("AUTHORIZED_OFFICIAL", "CONTROLLER"):
            raise HTTPException(status_code=403, detail="Department access denied")
    n.is_read = True
    db.commit()
    return {"id": n.id, "is_read": True}

@router.post("/read-all")
def mark_all_read(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(
        ((Notification.recipient_user_id == current_user.id) | (Notification.recipient_department_id == current_user.department_id)),
        Notification.is_read == False,
    )
    cnt = q.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"updated": cnt}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    # Auth via JWT query param
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id") or payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    # Load user via dedicated session (WebSocket cannot use request-scoped DI)
    from app.database import SessionLocal
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        dept_id = user.department_id
    finally:
        db_session.close()
    await manager.connect(websocket, user_id, dept_id)
    try:
        # Send initial unread count
        await websocket.send_text('{"type":"connected","message":"WebSocket connected"}')
        while True:
            # Keep alive, handle ping/pong
            data = await websocket.receive_text()
            # Echo or handle client ping
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, user_id, dept_id)

# Helper to create and push (used by other modules)
async def create_and_push(db: Session, recipient_user_id=None, recipient_department_id=None, type_="INFO", title="", message="", priority="NORMAL", **kwargs):
    # Persist first
    n = Notification(
        recipient_user_id=recipient_user_id,
        recipient_department_id=recipient_department_id,
        type=type_,
        title=title,
        message=message,
        priority=priority,
        **{k: v for k, v in kwargs.items() if k in ["section_id","track_id","block_request_id","optimized_block_id","integration_request_id"]}
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    # Then push via websocket (best effort, don't fail transaction)
    payload = {
        "type": "notification",
        "notification_id": n.id,
        "event": type_,
        "title": title,
        "message": message,
        "priority": priority,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
    try:
        if recipient_user_id:
            await manager.send_to_user(recipient_user_id, payload)
        elif recipient_department_id:
            await manager.send_to_department(recipient_department_id, payload)
    except Exception:
        pass
    return n
