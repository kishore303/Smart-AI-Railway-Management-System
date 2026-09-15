from typing import Dict, Set
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        # user_id -> set of websockets
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        # department_id -> set of websockets (for dept-scoped)
        self.dept_connections: Dict[int, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int, department_id: int):
        await websocket.accept()
        async with self.lock:
            self.user_connections.setdefault(user_id, set()).add(websocket)
            self.dept_connections.setdefault(department_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: int, department_id: int):
        async with self.lock:
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            if department_id in self.dept_connections:
                self.dept_connections[department_id].discard(websocket)
                if not self.dept_connections[department_id]:
                    del self.dept_connections[department_id]

    async def send_to_user(self, user_id: int, message: dict):
        # Persist-first already done, now push if online
        conns = self.user_connections.get(user_id, set()).copy()
        for ws in conns:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass

    async def send_to_department(self, department_id: int, message: dict):
        conns = self.dept_connections.get(department_id, set()).copy()
        for ws in conns:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass

    async def broadcast_to_users(self, user_ids: list, message: dict):
        for uid in user_ids:
            await self.send_to_user(uid, message)

manager = ConnectionManager()
